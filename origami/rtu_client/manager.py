"""
Subclass the Sending-based Websocket manager to serialize/deserialize json <-> RTU models,
and add some logging / exception handling hook.

Used by origami.rtu_client.client.RTUClient.

As a developer, you probably don't need to subclass this, just override Sending hooks like
.auth_hook and .init_hook inside your higher level class (e.g. RTUClient subclass / composition).
"""
import asyncio
import logging

from sending.backends.websocket import WebsocketManager

from origami.defs import rtu

# using vanilla logging instead of structlog with the expectation this moves to origami
logger = logging.getLogger(__name__)


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
    async def inbound_message_hook(self, contents: str):
        """
        Hook applied to every message coming in to us over the websocket before the message
        is passed to registered callback functions.

         - The validation server receives RTU Requests and emits RTU Replies
         - We're an RTU client, every message we get should parse into an RTU Reply
         - Registered callback functions should expect to take in an RTU Reply pydantic model
        """
        return rtu.GenericRTUReply.parse_raw(contents)

    async def outbound_message_hook(self, contents: rtu.GenericRTURequest):
        """
        Hook applied to every message we send out over the websocket.
         - Anything calling .send() should pass in an RTU Request pydantic model
        """
        return contents.json()

    # Logging and type hinting specific to RTU
    async def record_last_seen_message(self, message: rtu.GenericRTUReply):
        """
        Override WebsocketManager-defined method for type hinting and logging.
        This callback is registered as part of the WebsocketManager class, for
        debug and testing. It's used here as a natural logging entrypoint when
        we want to show all received RTU messages.
        """
        await super().record_last_seen_message(message)
        extra_dict = {
            "rtu_event": message.event,
            "rtu_transaction_id": str(message.transaction_id),
            "rtu_channel": message.channel,
        }
        if message.event == "new_delta_event":
            extra_dict["delta_type"] = message.data["delta_type"]
            extra_dict["delta_action"] = message.data["delta_action"]
        logger.debug(f"Received: {message.dict()}", extra=extra_dict)

    def send(self, message: rtu.GenericRTURequest):
        """Override WebsocketManager-defined method for type hinting and logging."""
        super().send(message)  # the .outbound_message_hook handles serializing this to json
        # all this extra stuff is just for logging
        msg = message.dict()
        extra_dict = {
            "rtu_event": msg["event"],
            "rtu_transaction_id": str(msg["transaction_id"]),
        }
        if msg["event"] == "new_delta_request":
            extra_dict["delta_type"] = msg["data"]["delta"]["delta_type"]
            extra_dict["delta_action"] = msg["data"]["delta"]["delta_action"]
        logger.debug(f"Sending: {msg}", extra=extra_dict)

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
