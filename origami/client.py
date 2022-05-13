"""The file holding client connection patterns for noteable APIs."""

import asyncio
import functools
from asyncio import Future
from collections import defaultdict
from logging import getLogger
from queue import LifoQueue
from typing import Optional, Type
from uuid import UUID, uuid4

import httpx
import websockets
from pydantic import BaseModel, ValidationError

from .types.rtu import (
    RTU_ERROR_HARD_MESSAGE_TYPES,
    RTU_MESSAGE_TYPES,
    AuthenticationReply,
    AuthenticationRequest,
    AuthenticationRequestData,
    CallbackTracker,
    FileSubscribeReplySchema,
    FileSubscribeRequestSchema,
    GenericRTUMessage,
    GenericRTUReply,
    GenericRTUReplySchema,
    GenericRTURequest,
    GenericRTURequestSchema,
    MinimalErrorSchema,
    PingReply,
    PingRequest,
    RTUEventCallable,
    TopicActionReplyData,
)

logger = getLogger('noteable.origami.client')


class NoteableClient(httpx.AsyncClient):
    """An async client class that provides interfaces for communicating with Noteable APIs."""

    NOTEABLE_DOMAIN = "app.noteable.world"
    NOTEABLE_BETA_URL = f"https://{NOTEABLE_DOMAIN}/"
    NOTEABLE_WEBSOCKET_URI = f"wss://{NOTEABLE_DOMAIN}/gate/api/v1/rtu"

    def _requires_ws_context(func):
        """A helper for checking if one is in a websocket context or not"""

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if self.rtu_socket is None:
                raise ValueError("Cannot send RTU request outside of a context manager scope.")
            return await func(self, *args, **kwargs)

        return wrapper

    def _default_timeout_arg(func):
        """A helper for checking if one is in a websocket context or not"""

        @functools.wraps(func)
        async def wrapper(self, *args, timeout=None, **kwargs):
            if timeout is None:
                timeout = self.ws_timeout
            return await func(self, *args, timeout=timeout, **kwargs)

        return wrapper

    def __init__(
        self, api_token, domain=NOTEABLE_DOMAIN, follow_redirects=True, ws_timeout=5, **kwargs
    ):
        """Initializes httpx client and sets up state trackers for async comms."""
        self.domain = domain
        self.token = api_token
        self.ws_timeout = ws_timeout
        self.rtu_socket = None
        self.process_task_loop = None

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f"Bearer {api_token}"
        # assert 'Authorization' in headers, "No API token present for authenticating requests"

        # Set of active channel subscriptions (always subscribed to system messages)
        self.subscriptions = {'system'}
        # channel -> message_type -> callback_queue
        self.type_callbacks = defaultdict(lambda: defaultdict(LifoQueue))
        # channel -> transaction_id -> callback_queue
        self.transaction_callbacks = defaultdict(lambda: defaultdict(LifoQueue))
        super().__init__(
            base_url=f"https://{domain}/",
            follow_redirects=follow_redirects,
            headers=headers,
            **kwargs,
        )

    @property
    def origin(self):
        """Formates the domain in an origin string for websocket headers."""
        return f'https://{self.domain}'

    @property
    def ws_uri(self):
        """Formats the websocket URI out of the notable domain name."""
        return f"wss://{self.domain}/gate/api/v1/rtu"

    async def __aenter__(self):
        """
        Creates an async test client for the Noteable App.

        An Authorization Bearer header must be present or Noteable
        returns a 403 immediately. Normally that bearer token is
        JWT format and the verify_jwt_token Security function would
        validate and extract principal-user-id from the token.
        """
        res = await httpx.AsyncClient.__aenter__(self)
        # Origin is needed or the server request crashes and rejects the connection
        headers = {'Authorization': self.headers['authorization'], 'Origin': self.origin}
        # raise ValueError(self.headers)
        self.rtu_socket = await websockets.connect(self.ws_uri, extra_headers=headers)
        # Loop indefinitely over the incoming websocket messages
        self.process_task_loop = asyncio.create_task(self._process_messages())
        # Ping to prove we're readily connected (enable if trying to determine if connecting vs auth is a problem)
        # await self.ping_rtu()
        # Authenticate for more advanced API calls
        await self.authenticate()
        return res

    async def __aexit__(self, exc_type, exc, tb):
        """Cleans out the tracker states and closes the httpx + websocket contexts."""
        try:
            if self.process_task_loop:
                self.process_task_loop.cancel()
                self.process_task_loop = None
            if self.rtu_socket:
                await self.rtu_socket.close()
                self.rtu_socket = None
            self.subscriptions = {'system'}
            # channel -> message_type -> callback_queue
            self.type_callbacks = defaultdict(lambda: defaultdict(LifoQueue))
            # channel -> transaction_id -> callback_queue
            self.transaction_callbacks = defaultdict(lambda: defaultdict(LifoQueue))
        except Exception:
            logger.exception("Error in closing out nested context loops")
        finally:
            return await httpx.AsyncClient.__aexit__(self, exc_type, exc, tb)

    def register_message_callback(
        self,
        callable: RTUEventCallable,
        channel: str,
        message_type: Optional[str] = None,
        transaction_id: Optional[UUID] = None,
        once: bool = True,
        response_schema: Optional[Type[BaseModel]] = None,
    ) -> CallbackTracker:
        """Registers a callback function that will be executed upon receiving the
        given message event type or transaction id in the specified topic channel.

        Multiple callbacks can exist against each callable.

        The once flag will indicate this callback should only be used for the next
        event trigger (default True).
        """
        tracker = CallbackTracker(
            once=once,
            count=0,
            callable=callable,
            channel=channel,
            message_type=message_type,
            transaction_id=transaction_id,
            next_trigger=Future(),
            response_schema=response_schema,
        )

        async def wrapped_callable(resp: GenericRTUMessage):
            """Wrapps the user callback function to handle message parsing and future triggers."""
            tracker.count += 1
            if resp.event in RTU_ERROR_HARD_MESSAGE_TYPES:
                resp = MinimalErrorSchema.parse_obj(resp)
                msg = resp.data['message']
                logger.exception(f"Request failed: {msg}")
                # TODO: Different exception class?
                tracker.next_trigger.set_exception(ValueError(msg))
            else:
                if tracker.response_schema:
                    resp = tracker.response_schema.parse_obj(resp)
                elif tracker.message_type in RTU_MESSAGE_TYPES:
                    resp = RTU_MESSAGE_TYPES[tracker.message_type].parse_obj(resp)

                try:
                    result = await callable(resp)
                except Exception as e:
                    logger.exception("Registered callback failed")
                    tracker.next_trigger.set_exception(e)
                else:
                    tracker.next_trigger.set_result(result)
            if not tracker.once:
                # Reset the next trigger promise
                tracker.next_trigger = Future()
                if tracker.transaction_id:
                    self.transaction_callbacks[tracker.channel][tracker.transaction_id].put_nowait(
                        tracker
                    )
                else:
                    self.type_callbacks[tracker.channel][tracker.message_type].put_nowait(tracker)

        # Replace the callable with a function that will manage itself and it's future awaitable
        tracker.callable = wrapped_callable
        if tracker.transaction_id:
            self.transaction_callbacks[channel][transaction_id].put_nowait(tracker)
        else:
            self.type_callbacks[channel][message_type].put_nowait(tracker)
        return tracker

    async def _process_messages(self):
        """Provides an infinite control loop for consuming RTU websocket messages.

        The loop will parse the message, convert to a RTUReply or RTURequest,
        log any validation errors (skipping callbacks), and finally identifying
        any callbacks that are registered to consume the given message and pass
        the message as the sole argument.
        """
        while True:
            # Release context control at the start of each loop
            await asyncio.sleep(0)
            try:
                msg = await self.rtu_socket.recv()
                if not isinstance(msg, str):
                    logger.exception(f"Unexepected message type found on socket: {type(msg)}")
                    continue
                try:
                    res = GenericRTUReply.parse_raw(msg)
                    channel = res.channel
                    event = res.event
                except ValidationError:
                    try:
                        res = GenericRTURequest.parse_raw(msg)
                        channel = res.channel
                        event = res.event
                    except ValidationError:
                        logger.exception(
                            f"Unexepected message found on socket: {msg[:30]}{'...' if len(msg) > 30 else ''}"
                        )
                        continue

                logger.debug(f"Received websocket message: {res}")
                # Check for transaction id responses
                id_lifo = self.transaction_callbacks[channel][res.transaction_id]
                while not id_lifo.empty():
                    tracker: CallbackTracker = id_lifo.get(block=False)
                    logger.debug(f"Found callable for {channel}/{tracker.transaction_id}")
                    await tracker.callable(res)
                type_lifo = self.type_callbacks[channel][event]
                # Check for general event callbacks
                while not type_lifo.empty():
                    tracker: CallbackTracker = type_lifo.get(block=False)
                    logger.debug(f"Found callable for {channel}/{event}")
                    await tracker.callable(res)

            except websockets.exceptions.ConnectionClosed:
                await asyncio.sleep(0)
                break
            except Exception:
                logger.exception("Unexpected callback failure")
                await asyncio.sleep(0)
                break

    @_requires_ws_context
    async def send_rtu_request(self, req: GenericRTURequestSchema):
        """Wraps converting a pydantic request model to be send down the websocket."""
        logger.debug(f"Sending websocket request: {req}")
        return await self.rtu_socket.send(req.json())

    @_requires_ws_context
    @_default_timeout_arg
    async def authenticate(self, timeout):
        """Authenticates a fresh websocket as the given user."""

        async def authorized(resp: AuthenticationReply):
            if resp.data.success:
                logger.debug("User is authenticated!")
                self.user = resp.data.user
            else:
                raise ValueError("Failed to authenticate websocket session")
            return resp

        # Register the transaction reply after sending the request
        req = AuthenticationRequest(
            transaction_id=uuid4(), data=AuthenticationRequestData(token=self.token)
        )
        req.data = AuthenticationRequestData(token=self.token)
        tracker = AuthenticationReply.register_callback(self, req, authorized)
        await self.send_rtu_request(req)
        # Give it timeout seconds to respond
        return await asyncio.wait_for(tracker.next_trigger, timeout)

    @_requires_ws_context
    @_default_timeout_arg
    async def ping_rtu(self, timeout):
        """Sends a ping request to the RTU websocket and confirms the response is valid."""

        async def pong(resp: GenericRTUReply):
            """The pong response for pinging a webrowser"""
            logger.debug("Intial ping response received! Websocket is live.")
            return resp  # Do nothing, we just want to ensure we reach the event

        # Register the transaction reply after sending the request
        req = PingRequest(transaction_id=uuid4())
        tracker = PingReply.register_callback(self, req, pong)
        await self.send_rtu_request(req)
        # Give it timeout seconds to respond
        pong_resp = await asyncio.wait_for(tracker.next_trigger, timeout)
        # These should be consistent, but validate for good measure
        assert pong_resp.transaction_id == req.transaction_id
        assert pong_resp.event == "ping_reply"
        assert pong_resp.channel == "system"
        return pong_resp

    def _gen_subscription_request(self, channel):
        async def process_subscribe(resp: GenericRTUReplySchema[TopicActionReplyData]):
            if resp.data.success:
                self.subscriptions.add(resp.channel)
            else:
                logger.error(f"Failed to subscribe to channel topic: {channel}")
            return resp

        # Register the reply first
        tracker = self.register_message_callback(
            process_subscribe,
            channel,
            transaction_id=uuid4(),
            response_schema=GenericRTUReplySchema[TopicActionReplyData],
        )
        req = GenericRTURequest(
            transaction_id=tracker.transaction_id, event="subscribe_request", channel=channel
        )
        return req, tracker

    @_requires_ws_context
    @_default_timeout_arg
    async def subscribe_channel(self, channel, timeout):
        """A generic pattern for subscribing to topic channels."""
        req, tracker = self._gen_subscription_request(channel)
        await self.send_rtu_request(req)
        return await asyncio.wait_for(tracker.next_trigger, timeout)

    def files_channel(self, file_id):
        """Helper to build file channel names from file ids"""
        return f"files/{file_id}"

    @_requires_ws_context
    @_default_timeout_arg
    async def subscribe_file(self, file_id, timeout):
        """Subscribes to a specified file for updates about it's contents."""
        channel = self.files_channel(file_id)
        req, tracker = self._gen_subscription_request(channel)
        tracker.response_schema = FileSubscribeReplySchema
        # TODO: set last_transaction_id from file payload
        # TODO: Handle delta catchups?
        # TODO: automate this
        # req.data.from_version_id = "381063aa-b18b-4533-8fb1-ae602b85fd7b"

        await self.send_rtu_request(req)
        return await asyncio.wait_for(tracker.next_trigger, timeout)
