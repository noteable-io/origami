"""
RTUClient is a high-level client for establishing a websocket connection, authenticating with a jwt,
subscribing to a file by version or last delta id, "squashing" Deltas into an in-memory Notebook
model, and registering callbacks for incoming RTU events by event_name and channel or incoming
Deltas by delta type and delta action.
"""
import asyncio
import logging
import traceback
import uuid
from typing import Awaitable, Callable, Dict, List, Literal, Optional, Type

import orjson
from pydantic import BaseModel, parse_obj_as
from sending.backends.websocket import WebsocketManager
from websockets.client import WebSocketClientProtocol

from origami.models.deltas.delta_types.cell_execute import CellExecute, CellExecuteAll
from origami.models.deltas.delta_types.nb_cells import (
    NBCellsAdd,
    NBCellsAddProperties,
    NBCellsDelete,
)
from origami.models.deltas.discriminators import FileDelta
from origami.models.notebook import CodeCell, NotebookCell
from origami.models.rtu.base import BaseRTUResponse
from origami.models.rtu.channels.files import (
    FileSubscribeReply,
    FileSubscribeRequest,
    NewDeltaEvent,
    NewDeltaRequest,
    NewDeltaRequestData,
)
from origami.models.rtu.channels.kernels import (
    BulkCellStateUpdateResponse,
    KernelStatusUpdateResponse,
)
from origami.models.rtu.channels.system import AuthenticateReply, AuthenticateRequest
from origami.models.rtu.discriminators import RTURequest, RTUResponse
from origami.notebook.builder import CellNotFound, NotebookBuilder

logger = logging.getLogger(__name__)


#
# Sending-based websocket transport manager, converts JSON <-> RTU from messages on the wire
# Used in RTUClient further down below
#
class RTUManager(WebsocketManager):
    """
    - Makes a connection to the RTU validation server
    - Handles reconnection if the validation server crashes
    - Serializes inbound messages to rtu.GenericRTUReply and outbound to rtu.GenericRTURequest
    - Adds extra logging kwargs for RTU event type and optional Delta type/action
    - Other classes that use this should add appropriate .auth_hook and .init_hook,
      and register callbacks to do something with RTU events (see RTUClient)
    """

    # Serializing inbound and outbound messages between websocket str payloads and RTU models
    async def inbound_message_hook(self, contents: str) -> RTUResponse:
        """
        Hook applied to every message coming in to us over the websocket before the message
        is passed to registered callback functions.

         - The validation server receives RTU Requests and emits RTU Replies
         - We're an RTU client, every message we get should parse into an RTU Reply
         - Registered callback functions should expect to take in an RTU Reply pydantic model
        """
        # Two-pass parsing, once to BaseRTUResponse to generate channel_prefix dervied value
        # then a second parse to go through the discriminators to a specific event (or fall back
        # to error or BaseRTUResponse)
        data: dict = orjson.loads(contents)
        data['channel_prefix'] = data.get('channel', '').split('/')[0]
        rtu_event = parse_obj_as(RTUResponse, data)

        # Debug Logging
        extra_dict = {
            "rtu_event": rtu_event.event,
            "rtu_transaction_id": str(rtu_event.transaction_id),
            "rtu_channel": rtu_event.channel,
        }
        if isinstance(rtu_event, NewDeltaEvent):
            extra_dict["delta_type"] = rtu_event.data.delta_type
            extra_dict["delta_action"] = rtu_event.data.delta_action
        logger.debug(f"Received: {data}\nParsed: {rtu_event.dict()}", extra=extra_dict)
        return rtu_event

    async def outbound_message_hook(self, contents: RTURequest) -> str:
        """
        Hook applied to every message we send out over the websocket.
         - Anything calling .send() should pass in an RTU Request pydantic model
        """
        return contents.json()

    def send(self, message: RTURequest) -> None:
        """Override WebsocketManager-defined method for type hinting and logging."""
        super().send(message)  # the .outbound_message_hook handles serializing this to json
        # all this extra stuff is just for logging
        extra_dict = {
            "rtu_event": message.event,
            "rtu_transaction_id": str(message.transaction_id),
        }
        if message.event == "new_delta_request":
            extra_dict["delta_type"] = message.data.delta.delta_type
            extra_dict["delta_action"] = message.data.delta.delta_action
        logger.debug("Sending: RTU request", extra=extra_dict)

    async def on_exception(self, exc: Exception):
        """
        Add a naive delay in reconnecting if we broke the websocket connection because
        there was a raised Exception in our _poll_loop, e.g. unserializable messages
        or syntax errors somewhere in our code.

        TODO: Make this elegant, perhaps a backoff strategy in Sending base.py
        """
        await super().on_exception(exc)
        # Sleep 1 second per number of reconnections we've made
        await asyncio.sleep(self.reconnections)


#
# Helpers for send delta request -> await Gate propogating new delta event or returning error
# Used in RTUClient further down below
#
class DeltaRejected(Exception):
    pass


# Used in registering callback functions that get called right after squashing a Delta
class DeltaCallback(BaseModel):
    # callback function should be async and expect one argument: a FileDelta
    # Doesn't matter what it returns. Pydantic doesn't validate Callable args/return.
    delta_class: Type[FileDelta]
    fn: Callable[[FileDelta], Awaitable[None]]


class DeltaRequestCallbackManager:
    """
    Don't use this directly, see RTUClient.new_delta_request which builds an instance of this and
    returns the .result -- Future resolves to bool or raises DeltaRejected

    - Sends over websocket to Gate
    - Registers RTU and Delta squashing callbacks to resolve the Future either when the Delta was
      successful and squashed into Notebook or when there was an error (Rejected / Invalid Delta)
    - Deregisters RTU and Delta callbacks when Future is resolved

    Use case:
    delta_squashed: asyncio.Future[bool] = await rtu_client.new_delta_request(...)
    try:
        await delta_squashed
    except DeltaRejected:
        ...
    # Delta is guarenteed to be in rtu_client.builder at this point
    """

    def __init__(self, client: 'RTUClient', delta: FileDelta):
        self.result = asyncio.Future()
        self.client = client
        self.delta = delta  # keep a ref to use in self.delta_cb_ref
        req = NewDeltaRequest(
            channel=f'files/{self.client.file_id}', data=NewDeltaRequestData(delta=delta)
        )
        # Register one cb by RTU request transaction id in order to catch errors and set Future
        self.rtu_cb_ref = client.register_transaction_id_callback(
            transaction_id=req.transaction_id, fn=self.rtu_cb
        )
        # Register other cb by Delta type so we'll be able to resolve future when it's squashed
        self.delta_cb_ref = client.register_delta_callback(
            delta_class=type(delta), fn=self.delta_cb
        )
        client.send(req)

    def deregister_callbacks(self):
        self.rtu_cb_ref()  # deregisters the callback from Sending managed list
        self.client.delta_callbacks.remove(self.delta_cb_ref)  # Remove from delta cb list

    async def rtu_cb(self, msg: RTUResponse):
        # If the delta is rejected, we should see a new_delta_reply with success=False and the
        # details are in a separate delta_rejected event
        if msg.event == "delta_rejected":
            logger.debug("Delta rejected", extra={"rtu_msg": msg})
            self.result.set_exception(DeltaRejected(msg.data["cause"]))
            self.deregister_callbacks()

        elif msg.event == "invalid_data":
            # If Gate can't parse the Delta into Pydantic model, it will give back this invalid_data
            # event, but it doesn't include the validation details in the body. Need to look at
            # Gate logs to see what happened (like nb_cells add not having 'id' in properties)
            logger.debug("Delta invalid", extra={"rtu_msg": msg})
            self.result.set_exception(DeltaRejected("Invalid Delta scheme"))
            self.deregister_callbacks()

        elif msg.event == "permission_denied":
            logger.debug("Delta permission denied", extra={"rtu_msg": msg})
            self.result.set_exception(DeltaRejected("Permission denied"))
            self.deregister_callbacks()

    async def delta_cb(self, delta: FileDelta):
        if delta.id == self.delta.id:
            logger.debug("Delta squashed", extra={'delta': delta})
            if not self.result.done():
                self.result.set_result(delta)
            self.deregister_callbacks()


#
# The meat of this file. RTUClient keeps an in-memory Notebook document model and Kernel/Cell state
# up to date by squashing received Deltas and observing state updates over RTU. Application code
# can register additional callbacks to take action on RTU or Delta events.
#
class RTUClient:
    def __init__(
        self,
        rtu_url: str,
        jwt: str,
        file_id: uuid.UUID,
        file_version_id: uuid.UUID,
        builder: NotebookBuilder,
        rtu_client_type: str = 'origami',
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
        self.rtu_client_type = rtu_client_type
        self.user_id = None  # set during authenticate_reply handling, used in new_delta_request

        self.rtu_session_id = None

        # Callbacks triggered from Sending based on websocket connection lifecycle events
        self.manager.auth_hook = self.auth_hook
        self.manager.connect_hook = self.connect_hook
        self.manager.context_hook = self.context_hook
        self.manager.disconnect_hook = self.disconnect_hook

        # Callbacks that are part of the startup flow (auth and File subscribe)
        self.register_rtu_event_callback(rtu_event=AuthenticateReply, fn=self._on_auth)
        self.register_rtu_event_callback(
            rtu_event=FileSubscribeReply, fn=self._on_file_subscribe_reply
        )

        # Incoming Delta handling. Key points here are:
        # - we don't want to squash deltas until we get file subscribe reply and deltas-to-apply
        # - Deltas may be "out of order", should save to be replayed later
        # - When finally applying Delta "in order", then we await callbacks by delta type/action
        # See self.new_delta_request for more details on sending out Deltas
        self.delta_callbacks: List[DeltaCallback] = []
        self.unapplied_deltas: List[FileDelta] = []  # "out of order deltas" to be replayed
        self.deltas_to_apply_event = asyncio.Event()  # set in ._on_file_subscribe_reply

        self.register_rtu_event_callback(rtu_event=NewDeltaEvent, fn=self._on_delta_recv)

        # Kernel and cell state handling
        self.kernel_state: str = None
        self.cell_states: Dict[str, str] = {}

        self.register_rtu_event_callback(
            rtu_event=KernelStatusUpdateResponse, fn=self.on_kernel_status_update
        )
        self.register_rtu_event_callback(
            rtu_event=BulkCellStateUpdateResponse, fn=self.on_bulk_cell_state_update
        )

        # Log anytime we get an un-modeled RTU message.
        # Not going through register_rtu_event_callback because isinstance would catch child classes
        def predicate_fn(topic: Literal[""], msg: RTUResponse):
            return type(msg) == BaseRTUResponse

        self.manager.register_callback(self._on_unmodeled_rtu_msg, on_predicate=predicate_fn)

        # When someone calls .execute_cell, return an asyncio.Future that will be resolved to be
        # the output collection id of the cell when it is finished running (or None if no output)
        self._execute_cell_events: Dict[str, asyncio.Future[Optional[uuid.UUID]]] = {}

    @property
    def cell_ids(self):
        """Return list of cell_id's in order from NotebookBuilder in-memory model"""
        return [cell.id for cell in self.builder.nb.cells]

    @property
    def kernel_pod_name(self) -> str:
        """Transform the file_id into the Pod name used to build the kernels/ RTU channel"""
        return f'kernels/notebook-kernel-{self.file_id.hex[:15]}'

    def send(self, msg: RTURequest):
        """
        Send an RTU message to Noteable. This is not async because what's happening behind the
        scenes is that RTUManager.send drops the RTU pydantic model onto an "outbound" asyncio.Queue
        then the "outbound worker" picks it up off the queue, serializes it to JSON, and sends it
        out over the wire.
        """
        self.manager.send(msg)

    async def _on_unmodeled_rtu_msg(self, msg: BaseRTUResponse):
        logger.warning("Received un-modeled RTU message", extra={"rtu_msg": msg})

    def register_rtu_event_callback(self, rtu_event: Type[RTUResponse], fn: Callable) -> Callable:
        """
        Register a callback that will be awaited whenever an RTU event is received that matches the
        other arguments passed in (event, channel, channel_prefix, transaction_id).
        """

        # When Sending/RTUManager receives and deserializes a message to an RTU event, it checks
        # every registered callback. If those have a "predicate_fn", it runs that fn against the
        # incoming message to decide whether to await the callback.
        # The "topic" in the predicate_fn is always hardcoded to "" in the websocket backend, it's
        # used in other backends like redis just not applicable here.
        def predicate_fn(topic: Literal[""], msg: RTUResponse):
            return isinstance(msg, rtu_event)

        return self.manager.register_callback(fn, on_predicate=predicate_fn)

    def register_transaction_id_callback(self, transaction_id: uuid.UUID, fn: Callable):
        """
        Register a callback that will be triggered whenever an RTU message comes in with a given
        transaction id. Useful for doing things like waiting for a reply / event or error to be
        propogated, e.g. for new delta requests.
        """

        def predicate_fn(topic: Literal[""], msg: RTUResponse):
            return msg.transaction_id == transaction_id

        return self.manager.register_callback(fn, on_predicate=predicate_fn)

    def register_delta_callback(self, delta_class: Type[FileDelta], fn: Callable):
        """
        Register a callback that may be triggered when we (eventually) apply an in-order Delta.

        RTUClient has a separate mechanism for registering delta callbacks from the vanilla
        Sending .register_callback flow because we don't necessarily want to run callbacks
        immediately when we observe a Delta come over the RTU websocket. We may be dealing
        with out-of-order deltas that are queued up and applied later on.

        These callbacks are triggered by .apply_delta() and stored in a separate callback
        list from vanilla Sending callbacks (manager.register_callback's)
        """
        cb = DeltaCallback(delta_class=delta_class, fn=fn)
        self.delta_callbacks.append(cb)
        return cb

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
        auth_request = AuthenticateRequest(
            data={'token': self.jwt, 'rtu_client_type': self.rtu_client_type}
        )

        # auth_hook is the special situation that shouldn't use manager.send(),
        # since that will ultimately delay sending things over the wire until
        # we observe the auth reply. Instead use the unauth_ws directly and manually serialize
        ws: WebSocketClientProtocol = await self.manager.unauth_ws
        logger.info(f"Sending auth request with jwt {self.jwt[:5]}...{self.jwt[-5:]}")
        await ws.send(auth_request.json())

    async def on_auth(self, msg: AuthenticateReply):
        # hook for Application code to override, consider catastrophic failure on auth failure
        if not msg.data.success:
            logger.error(f"Authentication failed: {msg.data}")

    async def _on_auth(self, msg: AuthenticateReply):
        """
        Callback for event='authenticate_reply' on 'system' channel.

        Application probably doesn't need to override this, override .on_auth instead which gets
        awaited before this method sends out the file subscribe request.
        """
        if msg.data.success:
            logger.info("Authentication successful")
            self.user_id = msg.data.user.id
            if self.manager.authed_ws.done():
                # We've seen that sometimes on websocket reconnect, trying to .authed_ws.set_result
                # throws an asyncio.InvalidStateError: Result is already set.
                # Still a mystery how this happens, Sending websocket backend resets the authed_ws
                # Future on websocket reconnect in a try / finally. If you figure it out, please
                # create an issue or PR!
                logger.warning("Authed websocket future already set, resetting to a new Future.")
                self.manager.authed_ws = asyncio.Future()

            self.manager.authed_ws.set_result(self.manager.unauth_ws.result())
            await self.send_file_subscribe()
        await self.on_auth(msg)

    async def send_file_subscribe(self):
        """
        Once `authenticate_reply` is observed, we should send the File subscription request.
        """
        # If our NotebookBuilder hasn't applied any deltas yet, then we should subscribe
        # by the version_id. That is, we think we've pulled down a clean seed Notebook by
        # s3 version id, and need to get deltas by the matching noteable version id.
        #
        # However if we've started applying deltas, such as after a Gate crash and RTU
        # reconnect, then subscribe by the last applied delta id.
        #
        # Note this also means file subscribe won't happen until after we've pulled down
        # the seed notebook from s3 for the first time, which is probably fine.
        #
        # Second note, subscribing by delta id all-0's throws an error in Gate.
        if self.builder.last_applied_delta_id and self.builder.last_applied_delta_id != uuid.UUID(int=0):  # type: ignore # noqa: E501
            req = FileSubscribeRequest(
                channel=f'files/{self.file_id}',
                data={'from_delta_id': self.builder.last_applied_delta_id},
            )
            logger.info(
                "Sending File subscribe request by last applied delta id",
                extra={'from_delta_id': str(req.data.from_delta_id)},
            )
        else:
            req = FileSubscribeRequest(
                channel=f'files/{self.file_id}',
                data={'from_version_id': self.file_version_id},
            )
            logger.info(
                "Sending File subscribe request by version id",
                extra={'from_version_id': str(req.data.from_version_id)},
            )
        self.manager.send(req)

    async def on_file_subscribe(self, msg: FileSubscribeReply):
        # hook for Application code to override if it wants to do something special with
        # file subscribe reply event on files/{self.file-id} channel
        pass

    async def _on_file_subscribe_reply(self, msg: FileSubscribeReply):
        """
        Callback for event 'subscribe_reply' on 'files/{self.file-id}' channel

        The file subscribe reply contains a bunch of information including which users are
        subscribed to the Notebook (has it open in their browser), which Application code may care
        about and want to handle in .on_file_subscribe.

        Here the main concern is to handle "deltas to apply", which are any deltas that have been
        created in between when our seed notebook version id was "squashed" and when we subscribed
        to the file by version id / last delta id.
        """
        # Kernel and cell states if there is a live Kernel
        if msg.data.kernel_session:
            self.kernel_state = msg.data.kernel_session.execution_state
        if msg.data.cell_states:
            self.cell_states = {item.cell_id: item.state for item in msg.data.cell_states}

        # Go through "Delta catchup" and signal to ourselves that we can begin handling any new
        # deltas coming in over the websocket. It's important not to start squashing incoming
        # deltas until after we get the file subscribe and replay "deltas to apply" if there are any
        for delta in msg.data.deltas_to_apply:
            await self.queue_or_apply_delta(delta=delta)

        self.deltas_to_apply_event.set()
        # Prepare to replay any Deltas we received while waiting for file subscribe response.
        # If we had deltas to apply, then Notebook Builder has a last applied delta id.
        # If we did not, then we rely on Gate to have told us where the "root" of our deltas
        # starts, so we don't apply deltas out of order at the start.
        if not self.builder.last_applied_delta_id:
            self.builder.last_applied_delta_id = msg.data.latest_delta_id
        await self.replay_unapplied_deltas()
        # Now all "Delta catchup" and "inflight Deltas" have been processed.
        # Application code may want to do extra things like subscribe to kernels channel or users
        # channel for each msg.data['user_subscriptions'].
        await self.on_file_subscribe(msg)

    async def _on_delta_recv(self, msg: NewDeltaEvent):
        """
        Extract delta from GenericRTUReply and delegate to .queue_or_apply_delta
        """
        # We may receive RTU / Delta events while we're still waiting to get a file_subscribe
        # reply, which contains "delta catchup" which need to be applied before new deltas.
        # We shot ourselves in the foot once by waiting for the deltas_to_apply_event in this method
        # but that blocks handling any other received websocket/RTU messages. Instead, the right
        # thing to do is probably add these to the unapplied_deltas list if we haven't done delta
        # catchup yet.
        if not self.deltas_to_apply_event.is_set():
            self.unapplied_deltas.append(msg.data)
        else:
            await self.queue_or_apply_delta(delta=msg.data)

    async def queue_or_apply_delta(self, delta: FileDelta):
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

    async def post_queue_delta(self, delta: FileDelta):
        """
        Hook for Application code to override if it wants to do something special when queueing
        "out of order" Deltas.
        """
        pass

    async def pre_apply_delta(self, delta: FileDelta):
        """
        Hook for Application code to override if it wants to do something special before running
        "squashing" Delta into NotebookBuilder and running applicable callbacks.
        """
        pass

    async def failed_to_squash_delta(self, delta: FileDelta, exc: Exception):
        """
        Hook for Application code to override when a Delta fails to "squash" into the in-memory
        Notebook representation.
        """
        pass

    async def apply_delta(self, delta: FileDelta):
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
            if isinstance(delta, dc.delta_class):
                # Add coroutine to the callbacks list
                callbacks.append(dc.fn(delta))

        # Log errors on callbacks but don't stop RTU processing loop
        results = await asyncio.gather(*callbacks, return_exceptions=True)
        for callback, result in zip(callbacks, results):
            if isinstance(result, Exception):
                logger.error(
                    "Error trying to run callback while applying delta",
                    exc_info="".join(traceback.format_tb(result.__traceback__)),
                    extra={
                        'callback': callback,
                        'delta': delta,
                        'ename': repr(result),
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
                    "Applying previously queued out of order delta",
                    extra={'delta_id': str(delta.id)},
                )
                await self.apply_delta(delta=delta)
                self.unapplied_deltas.remove(delta)
                return await self.replay_unapplied_deltas()

    # Kernel and Cell states
    async def on_kernel_status_update(self, msg: KernelStatusUpdateResponse):
        """Called when we receive a kernel_status_update_event on kernels/ channel"""
        self.kernel_state = msg.data.kernel.execution_state
        logger.info(f"updating Kernel state to: {self.kernel_state}")

    async def on_bulk_cell_state_update(self, msg: BulkCellStateUpdateResponse):
        """Called when we receive a bulk_cell_state_update_event on kernels/ channel"""
        self.cell_states = {}
        for item in msg.data.cell_states:
            if item.cell_id in self._execute_cell_events:
                # When we see that a cell we're monitoring has finished, resolve the Future to
                # be the cell output collection id.
                if item.state in ['finished_with_error', 'finished_with_no_error']:
                    logger.info(
                        "Cell execution for monitored cell finished",
                        extra={
                            'cell_id': item.cell_id,
                            'state': item.state,
                        },
                    )
                    fut = self._execute_cell_events[item.cell_id]
                    if not fut.done():
                        try:
                            _, cell = self.builder.get_cell(item.cell_id)
                            fut.set_result(cell.output_collection_id)
                        except CellNotFound:
                            logger.warning(
                                "Cell execution finished for cell that doesn't exist in Notebook",
                                extra={
                                    'cell_id': item.cell_id,
                                    'state': item.state,
                                },
                            )
                            fut.set_exception(CellNotFound(item.cell_id))
            self.cell_states[item.cell_id] = item.state
        logger.debug("Updated cell states", extra={'cell_states': self.cell_states})

    async def wait_for_kernel_idle(self):
        """Wait for the kernel to be idle"""
        logger.info("Waiting for Kernel to be idle")
        while self.kernel_state != 'idle':
            await asyncio.sleep(0.05)
        logger.info("Kernel is idle")

    async def new_delta_request(self, delta=FileDelta) -> FileDelta:
        """
        Send a new delta request to the server and wait for it to have been accepted and propogated
        to other clients, as well as squashed into our own in-memory Notebook.
        Raises errors if the Delta was rejected for any reason.
        """
        req = DeltaRequestCallbackManager(client=self, delta=delta)
        return await req.result

    async def add_cell(
        self, cell: Optional[NotebookCell] = None, after_id: Optional[str] = None
    ) -> NotebookCell:
        if not cell:
            cell = CodeCell()
        props = NBCellsAddProperties(cell=cell, after_id=after_id, id=cell.id)
        delta = NBCellsAdd(file_id=self.file_id, properties=props)
        await self.new_delta_request(delta)
        return cell

    async def delete_cell(self, cell_id: str) -> None:
        delta = NBCellsDelete(file_id=self.file_id, properties={'id': cell_id})
        await self.new_delta_request(delta)

    async def execute_cell(self, cell_id: str) -> asyncio.Future[Optional[uuid.UUID]]:
        """
        Send a new delta request for cell execution by cell id. The returned Future will be resolved
        to the output collection id of the Cell when it has finished running (or None if there is
        no output).
        """
        execute_event = asyncio.Future()
        self._execute_cell_events[cell_id] = execute_event
        delta = CellExecute(file_id=self.file_id, resource_id=cell_id)
        await self.new_delta_request(delta)
        return execute_event

    async def execute_all(self) -> List[asyncio.Future[Optional[uuid.UUID]]]:
        for cell_id in self.cell_ids:
            self._execute_cell_events[cell_id] = asyncio.Future()
        delta = CellExecuteAll(file_id=self.file_id)
        await self.new_delta_request(delta)
        return list(self._execute_cell_events.values())
