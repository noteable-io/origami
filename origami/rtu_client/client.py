"""
RTUClient is a high-level client for establishing a websocket connection, authenticating with a jwt,
subscribing to a file by version or last delta id, "squashing" Deltas into an in-memory Notebook
model, and registering callbacks for incoming RTU events by event_name and channel or incoming
Deltas by delta type and delta action.
"""
import asyncio
import traceback
import uuid
from typing import Awaitable, Callable, List, Literal, Optional

import structlog
from pydantic import BaseModel
from websockets.client import WebSocketClientProtocol

from origami.defs import deltas, rtu
from origami.notebook.builder import NotebookBuilder
from origami.rtu_client.manager import RTUManager

logger = structlog.get_logger(__name__)


class DeltaCallback(BaseModel):
    # callback function should be async and expect one argument: a FileDelta
    # Doesn't matter what it returns. Pydantic doesn't validate Callable args/return.
    fn: Callable[[deltas.FileDelta], Awaitable[None]]
    # If left at * / *, callback will match on all Deltas types and actions
    # If delta_type is 'execute' and delta_action is still *, it would match
    # on all actions (e.g 'execute' and 'execute_all')
    delta_type: str = "*"
    delta_action: str = "*"


class RTUClient:
    def __init__(
        self, rtu_url: str, jwt: str, file_id: str, file_version_id: str, builder: NotebookBuilder
    ):
        """
        High-level client over the Sending websocket backend / RTUManager (serialize websocket msgs
        to/from RTU models) that allows you to add callbacks by RTU event type or Delta type/action.

        - On .initialize(), will make a websocket connection to {rtu_url}
          - RTUManager / Sending websocket backend handles reconnection
          - RTUClient sets .manager.auth_hook to kick off the auth request, don't override that
          - awaits .on_websocket_connect() hook that you can override in application code

        - After websocket connection is established, sends authenticate_request on system channel
          - Has a callback registered for 'authenticate_reply' on system channel which will
            await .on_auth (hook to define in application code) then send file subscribe request

        - After authentication, sends subscribe_request to files/{file_id} channel
          - awaits .on_file_subscribe() hook that you can override in application code

        - Use .register_rtu_event_callback to register callbacks that are run against RTU messages

        - Use .register_delta_callback to register callbacks that are run against Deltas
          - May not run when message is initially received if the Delta is "out of order", RTUClient
            handles queueing and replaying out of order deltas
          - Callbacks run after the Delta is "squashed" into {builder}
        """
        self.manager = RTUManager(ws_url=rtu_url)  # Sending websocket backend w/ RTU serialization
        self.jwt = jwt
        self.file_id = file_id
        self.file_version_id = file_version_id
        self.builder = builder

        # rtu_session_id, and the connect / disconnect / context hooks are used solely for logging.
        # It adds rtu_session_id, kernel_session_id, rtu_file_id, and rtu_file_name as structlog
        # contextvars to all callback functions
        self.rtu_session_id = None
        self.manager.auth_hook = self.auth_hook
        self.manager.connect_hook = self.connect_hook
        self.manager.context_hook = self.context_hook
        self.manager.disconnect_hook = self.disconnect_hook

        self.register_rtu_event_callback(
            fn=self._on_auth,
            event_type="authenticate_reply",
            channel="system",
        )

        self.register_rtu_event_callback(
            fn=self._on_file_subscribe_reply,
            event_type="subscribe_reply",
            channel=f"files/{file_id}",
        )

        # Delta handling. Key points here are:
        # - we don't want to apply deltas until we get file subscribe reply and deltas-to-apply
        # - Deltas may be "out of order", should save to be replayed later
        # - When finally applying Delta "in order", then we await callbacks by delta type/action
        self.delta_callbacks: List[DeltaCallback] = []
        self.unapplied_deltas: List[deltas.FileDelta] = []  # "out of order deltas" to be replayed
        self.deltas_to_apply_event = asyncio.Event()  # set in ._on_file_subscribe_reply

        self.register_rtu_event_callback(
            fn=self._on_delta_recv,
            event_type="new_delta_event",
            channel=f"files/{file_id}",
        )

    def send(self, msg: rtu.GenericRTURequest):
        """
        Send an RTU message to Noteable. This is not async because what's happening behind the
        scenes is that RTUManager.send drops the RTU pydantic model onto an "outbound" asyncio.Queue
        then the "outbound worker" picks it up off the queue, serializes it to JSON, and sends it
        out over the wire.
        """
        self.manager.send(msg)

    def register_rtu_event_callback(
        self,
        fn: Callable,
        event_type: str,
        channel: Optional[str] = None,
        channel_prefix: Optional[str] = None,
    ):
        """
        Register a callback that will be awaited whenever an RTU event is received that matches the
        {event_type} and optionally the {channel} or starts with {channel_prefix}. It's adviseable
        to use {channel} if you can, but in cases such as registering a callback for users/<id>
        (user preference updates) it might be easier to use {channel_prefix}.
        """

        # When Sending/RTUManager receives and deserializes a message to an RTU event, it checks
        # every registered callback. If those have a "predicate_fn", it runs that fn against the
        # incoming message to decide whether to await the callback.
        # The "topic" in the predicate_fn is always hardcoded to "" in the websocket backend, it's
        # used in other backends like redis just not applicable here.
        def predicate_fn(topic: Literal[""], msg: rtu.GenericRTUReply):
            if msg.event == event_type:
                if channel and msg.channel == channel:
                    return True
                elif channel_prefix and msg.channel.startswith(channel_prefix):
                    return True
            return False

        return self.manager.register_callback(fn, on_predicate=predicate_fn)

    def register_delta_callback(self, fn: Callable, delta_type: str = "*", delta_action: str = "*"):
        """
        Register a callback that may be triggered when we (eventually) apply an in-order Delta.

        RTUClient has a separate mechanism for registering delta callbacks from the vanilla
        Sending .register_callback flow because we don't necessarily want to run callbacks
        immediately when we observe a Delta come over the RTU websocket. We may be dealing
        with out-of-order deltas that are queued up and applied later on.

        These callbacks are triggered by .apply_delta() and stored in a separate callback
        list from vanilla Sending callbacks (manager.register_callback's)
        """
        self.delta_callbacks.append(
            DeltaCallback(fn=fn, delta_type=delta_type, delta_action=delta_action)
        )

    async def initialize(self, queue_size=0, inbound_workers=1, outbound_workers=1, poll_workers=1):
        # see Sending base.py for details, calling .initialize starts asyncio.Tasks for
        # - processing messages coming over the wire, dropping them onto inbound queue
        # - taking messages taken off the inbound queue and running callbacks
        # - taking messages from outbound queue and sending them over the wire
        # - if queue_size is 0, it means no max queue size for inbound/outbound asyncio.Queue
        await self.manager.initialize(
            queue_size=queue_size,
            inbound_workers=inbound_workers,
            outbound_workers=outbound_workers,
            poll_workers=poll_workers,
        )

    async def shutdown(self, now: bool = False):
        await self.manager.shutdown(now=now)

    # See Sending backends.websocket for details but a quick refresher on hook timing:
    # - context_hook is called within the while True loop for inbound worker, outbound worker,
    #   and poll_worker, it's for binding contextvars to every function call
    # - connect_hook is called on websocket connect/reconnect, after resolving .unauth_ws future
    # - auth_hook is called after connect_hook
    # - init_hook is called after auth_hook
    # - disconnect_hook is called when websocket disconnects, before reconnect attempt
    # Re: *args / **kwargs in all hooks except context_hook below: Sending passes 'self' (mgr)
    # as an arg to those, but we don't need to use it since we have self.manager to ref.
    async def context_hook(self):
        # In application code, might want to put structlog.bind_contextvars here
        pass

    async def connect_hook(self, *args, **kwargs):
        ws: WebSocketClientProtocol = await self.manager.unauth_ws
        self.rtu_session_id = ws.response_headers.get("rtu_session_id")

    async def disconnect_hook(self, *args, **kwargs):
        self.rtu_session_id = None

    async def auth_hook(self, *args, **kwargs):
        """
        Called after the websocket connection is established. This also implicitly makes it so
        .send() / ._publish will effectively suspend sending messages over the websocket
        until we've observed an `authenticate_reply` event
        """
        auth_request = rtu.AuthenticationRequest(
            transaction_id=uuid.uuid4(), data=rtu.AuthenticationRequestData(token=self.jwt)
        )
        # auth_hook is the special situation that shouldn't use manager.send(),
        # since that will ultimately delay sending things over the wire until
        # we observe the auth reply. Instead use the unauth_ws directly and manually serialize
        ws: WebSocketClientProtocol = await self.manager.unauth_ws
        logger.info(f"Sending auth request with jwt {self.jwt[:5]}...{self.jwt[-5:]}")
        await ws.send(auth_request.json())

    async def on_auth(self, msg: rtu.GenericRTUReply):
        # hook for Application code to override if it wants to do something special with
        # authenticate_reply event on system channel
        pass

    async def _on_auth(self, msg: rtu.GenericRTUReply):
        """
        Callback for event='authenticate_reply' on 'system' channel.

        Application probably doesn't need to override this, override .on_auth instead which gets
        awaited before this method sends out the file subscribe request.
        """
        if msg.data["success"]:
            logger.info("Authentication successful")
            if self.manager.authed_ws.done():
                # We've seen that sometimes on websocket reconnect, trying to .authed_ws.set_result
                # throws an asyncio.InvalidStateError: Result is already set.
                # Still a mystery how this happens, Sending websocket backend resets the authed_ws
                # Future on websocket reconnect in a try / finally. If you figure it out, please
                # PR sending or origami!
                logger.warning("Authed websocket future already set, resetting to a new Future.")
                self.manager.authed_ws = asyncio.Future()

            self.manager.authed_ws.set_result(self.manager.unauth_ws.result())
            await self.on_auth(msg)
            await self.send_file_subscribe()
        else:
            logger.error(f"Authentication failed: {msg}")

    async def send_file_subscribe(self):
        """
        Once `authenticate_reply` is observed, we should send the File subscription request.
        """
        channel = f"files/{self.file_id}"
        event = "subscribe_request"
        # If our NotebookBuilder hasn't applied any deltas yet, then we should subscribe
        # by the version_id. That is, we think we've pulled down a clean seed Notebook by
        # s3 version id, and need to get deltas by the matching noteable version id.
        #
        # However if we've started applying deltas, such as after a Gate crash and RTU
        # reconnect, then subscribe by the last applied delta id.
        #
        # Note this also means file subscribe won't happen until after we've pulled down
        # the seed notebook from s3 for the first time, which is probably fine.
        if self.builder.last_applied_delta_id:
            data = rtu.FileSubscribeRequestData(from_delta_id=self.builder.last_applied_delta_id)
            logger.info(
                "Sending File subscribe request by last applied delta id",
                extra={'from_delta_id': str(data.from_delta_id)},
            )
        else:
            data = rtu.FileSubscribeRequestData(from_version_id=self.file_version_id)
            logger.info(
                "Sending File subscribe request by version id",
                from_version_id=str(data.from_version_id),
            )
        req = rtu.FileSubscribeRequestSchema(
            transaction_id=uuid.uuid4(),
            event=event,
            channel=channel,
            data=data,
        )
        self.manager.send(req)

    async def on_file_subscribe(self, msg: rtu.GenericRTUReply):
        # hook for Application code to override if it wants to do something special with
        # file subscribe reply event on files/{self.file-id} channel
        pass

    async def _on_file_subscribe_reply(self, msg: rtu.GenericRTUReply):
        """
        Callback for event 'subscribe_reply' on 'files/{self.file-id}' channel

        The file subscribe reply contains a bunch of information including which users are
        subscribed to the Notebook (has it open in their browser), which Application code may care
        about and want to handle in .on_file_subscribe.

        Here the main concern is to handle "deltas to apply", which are any deltas that have been
        created in between when our seed notebook version id was "squashed" and when we subscribed
        to the file by version id / last delta id.
        """
        # Go through "Delta catchup" and signal to ourselves that we can begin handling any new
        # deltas coming in over the websocket. It's important not to start squashing incoming
        # deltas until after we get the file subscribe and replay "deltas to apply" if there are any
        for item in msg.data["deltas_to_apply"]:
            delta = deltas.FileDelta.parse_obj(item)
            await self.queue_or_apply_delta(delta=delta)

        self.deltas_to_apply_event.set()
        # Prepare to replay any Deltas we received while waiting for file subscribe response.
        # If we had deltas to apply, then Notebook Builder has a last applied delta id.
        # If we did not, then we rely on Gate to have told us where the "root" of our deltas
        # starts, so we don't apply deltas out of order at the start.
        if not self.builder.last_applied_delta_id:
            # 'latest_delta_id' should /always/ be included in file subscribe reply
            self.builder.last_applied_delta_id = uuid.UUID(msg.data["latest_delta_id"])
        await self.replay_unapplied_deltas()
        # Now all "Delta catchup" and "inflight Deltas" have been processed.
        # Application code may want to do extra things like subscribe to kernels channel or users
        # channel for each msg.data['user_subscriptions'].
        await self.on_file_subscribe(msg)

    async def _on_delta_recv(self, msg: rtu.GenericRTUReply):
        """
        Extract delta from GenericRTUReply and delegate to .queue_or_apply_delta
        """
        # We may receive RTU / Delta events while we're still waiting to get a file_subscribe
        # reply, which contains "delta catchup" which need to be applied before new deltas.
        # We shot ourselves in the foot once by waiting for the deltas_to_apply_event in this method
        # but that blocks handling any other received websocket/RTU messages. Instead, the right
        # thing to do is probably add these to the unapplied_deltas list if we haven't done delta
        # catchup yet.
        delta = deltas.FileDelta.parse_obj(msg.data)
        if not self.deltas_to_apply_event.is_set():
            self.unapplied_deltas.append(delta)
        else:
            await self.queue_or_apply_delta(delta=delta)

    async def queue_or_apply_delta(self, delta: deltas.FileDelta):
        """
        Checks whether we're able to apply the Delta by comparing its
        parent_delta_id with the last_applied_delta_id in the NBBuilder.
        If it is not a match, we may have received out of order deltas and we
        queue it to be replayed later
        """
        if self.builder.last_applied_delta_id is None:
            # We need this for situations where we've downloaded the seed notebook and gotten deltas
            # to apply from file subscribe reply, but do not have information about what the first
            # delta in that deltas-to-apply list is.
            await self.apply_delta(delta=delta)

        elif delta.parent_delta_id == self.builder.last_applied_delta_id:
            # For logging related to applying delta, override .pre_apply_delta
            await self.apply_delta(delta=delta)
            await self.replay_unapplied_deltas()

        else:
            # For logging related to queueing "out of order" Deltas, override .post_queue_delta
            self.unapplied_deltas.append(delta)
            await self.post_queue_delta(delta=delta)

    async def post_queue_delta(self, delta: deltas.FileDelta):
        """
        Hook for Application code to override if it wants to do something special when queueing
        "out of order" Deltas.
        """
        pass

    async def pre_apply_delta(self, delta: deltas.FileDelta):
        """
        Hook for Application code to override if it wants to do something special before running
        "squashing" Delta into NotebookBuilder and running applicable callbacks.
        """
        pass

    async def failed_to_squash_delta(self, delta: deltas.FileDelta, exc: Exception):
        """
        Hook for Application code to override when a Delta fails to "squash" into the in-memory
        Notebook representation.
        """
        pass

    async def apply_delta(self, delta: deltas.FileDelta):
        """
        Squash a Delta into the NotebookBuilder and run applicable callbacks

         - If squashing a Delta into the in-memory Notebook representation fails for some reason,
           then PA basically needs to crash because all follow on Delta application is very suspect
           (e.g. future deltas think a cell exists when it doesn't, or content exists, etc)
         - If callbacks are triggered, it is okay for them to fail and we just log it because those
           are generally just side-effects, not core to applying future deltas

        Note on alternative approach to handling delta squashing failures: @Seal suggested
        redownloading Notebook and starting from latest delta rather than killing Kernel Pod but
        we don't have great comm mechanisms for PA to tell Gate to squash the problematic Delta or
        to figure out the most recent version in Cockroach / S3. For now, killing Kernel Pod on
        NotebookBuilder apply and logging errors on side-effect callbacks is the best we can do.
        """
        await self.pre_apply_delta(delta=delta)
        try:
            # "squash" delta into in-memory notebook representation
            self.builder.apply_delta(delta)
        except Exception as e:
            await self.failed_to_squash_delta(delta=delta, exc=e)

        # Run applicable callbacks concurrently, await all of them completing.
        callbacks = []
        for dc in self.delta_callbacks:
            if dc.delta_type == "*" or dc.delta_type == delta.delta_type:
                if dc.delta_action == "*" or dc.delta_action == delta.delta_action:
                    callbacks.append(dc.fn(delta))
        # Log errors on callbacks but don't shut down Kernel Pod
        results = await asyncio.gather(*callbacks, return_exceptions=True)
        for callback, result in zip(callbacks, results):
            if isinstance(result, Exception):
                logger.error(
                    "Error trying to run callback while applying delta",
                    exc_info="".join(traceback.format_tb(result.__traceback__)),
                    extra={
                        'callback': callback,
                        'delta': delta,
                        'traceback': "".join(traceback.format_tb(result.__traceback__)),
                    },
                )

    async def replay_unapplied_deltas(self):
        """
        Attempt to apply any previous unapplied Deltas that were received out of order.
        Calls itself recursively in case replaying unapplied deltas resulted in multiple
        Deltas now being able to be applied. E.g. we received in order:
         - {'id': 2, 'parent_id': 1} # applied because NBBuilder had no last_applied_delta_id
         - {'id': 5, 'parent_id': 4} # queued because parent_id doesn't match builder
         - {'id': 4, 'parent_id': 3} # queued because parent_id doesn't match builder
         - {'id': 3, 'parent_id': 2} # applied, then needs to replay queued deltas

        Replaying would make the third received delta be applied, which would let
        replaying again also apply the second delta.
        """
        for delta in self.unapplied_deltas:
            if delta.parent_delta_id == self.builder.last_applied_delta_id:
                logger.debug(
                    "Applying previously queued out of order delta", delta_id=str(delta.id)
                )
                await self.apply_delta(delta=delta)
                self.unapplied_deltas.remove(delta)
                return await self.replay_unapplied_deltas()
