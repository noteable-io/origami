"""Defines the types involved with RTU communications"""

import enum
from asyncio import Future
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel, Field, root_validator, validator
from pydantic.generics import GenericModel

from .deltas import (
    CellContentsDeltaRequestDataWrapper,
    CellState,
    CellStateMessage,
    FileDelta,
    NewFileDeltaData,
)
from .kernels import KernelDetails
from .models import NoteableAPIModel, User

RTUData = TypeVar("RTUData")


class GenericRTURequestSchema(GenericModel, Generic[RTUData]):
    """The schema that all request payload utilize as a base. Typically
    the only field that differes is the `data` attribute that can be class
    dynamic for subclasses.
    """

    # This transaction id, if defined by the request, will be present in all replies spawned from this message.
    # Can be any arbitrary string, but we expect this will be most commonly formatted
    # as a randomly generated ID (UUID) and a timestamp.
    # Helpful for any client listeners that may be expecting a reply before applying a state change,
    # or need an identifier to know that a reply was generated from this client and can be ignored.
    transaction_id: UUID

    # A unique key explaining the action being taken by the client.
    # Event keys are universally unique, and each event key should have its own
    # schema for the data attribute below.
    # All backend routing will be done based on the event key.
    event: str

    # A specific channel, or URI, that the request is meant to be processed by.
    # Will usually take the form of :resource/:id (ex. files/uuid-go-here).
    # By convention events that have some RBAC element to them will look at the channel
    # to discover the relevant ID.

    # Breaking schema updates will be represented by a change in the URI format.
    # Example: files/uuid-go-here vs. filesV2/uuid-go-here. Version compatibility
    # could be supported by either the client or the server publishing to multiple channels.
    channel: str

    # Each event will have its own schema for this data object. Data objects for requests should
    # represent additional parameters on the event. Example: There could be a cell-run action that
    # includes the cell-id as an attribute on the data object.
    data: Optional[RTUData]

    @validator("event", "channel")
    def enforce_lowercase(cls, v):
        """Forces channel to always be lowercase"""
        return v.lower()

    class Config:
        """Allows for the optional RTU field type"""

        arbitrary_types_allowed = True


class GenericRTUReplySchema(GenericModel, Generic[RTUData]):
    """The schema that all response payload utilize as a base. Typically
    the only field that differes is the `data` attribute that can be class
    dynamic for subclasses.
    """

    executing_user_id: Optional[UUID] = None

    # The optional transaction ID given by the client during the request
    transaction_id: UUID

    # A message ID injected by the server.
    # This can be used by the client or server to ensure that the same message
    # isn't processed more than once, if we migrate from Redis to something that
    # guarantees a message is delivered at least once.
    msg_id: UUID

    # The unique event key for the frontend to route to its own state updates, if needed.
    # This should be different that the request event, similar to how Jupyter has execute_request
    # and execute_reply.
    event: str

    # The channel this event is being published on e.g. files/file-id-go-here
    channel: str

    # Optional data attributes. The schema for this is related to the event key. Data models related
    # to real-time updates will live here, along with any necessary metadata.

    # NOTE: For delta event this should always send HEAD^
    data: RTUData

    processed_timestamp: datetime

    @validator("event", "channel")
    def enforce_lowercase(cls, v):
        """Forces channel to always be lowercase"""
        return v.lower()

    @classmethod
    def register_callback(
        cls, client, request: GenericRTURequestSchema, func: 'RTUEventCallable'
    ) -> 'CallbackTracker':
        """Registers an async function that will consume the given request message coming
        from the client field. This enables a 'reply' operation against a transaction or
        message type to be responded to whenever the client sees the matching response
        payload.
        """
        return client.register_message_callback(
            func, request.channel, transaction_id=request.transaction_id, response_schema=cls
        )


GenericRTURequest = GenericRTURequestSchema[Optional[Dict]]
GenericRTUReply = GenericRTUReplySchema[Optional[Dict]]
GenericRTUMessage = Union[GenericRTURequest, GenericRTUReply]
RTUEventCallable = Callable[[GenericRTUMessage], Awaitable[Any]]


class CallbackTracker(BaseModel):
    """The class model used within origami to register a callback action upon a
    message response or topic event.

    The channel field specifies the subscription to monitor and then either a
    transaction_id or a message_type is used to identify messages that should
    run the callable against asynchronously.

    The next_trigger is the future object that one can await to know that the
    callabable has been made.

    A response schema can be used to coerce the response payload to a paricular
    pydantic model automatically if the general message consumer doesn't
    automatically detect it's type information.
    """

    once: bool
    count: int
    callable: RTUEventCallable
    channel: str
    message_type: Optional[str]
    transaction_id: Optional[UUID]
    response_schema: Optional[Type[BaseModel]]
    next_trigger: Future

    @root_validator
    def either_type_or_transaction(cls, values):
        """Ensures that we have one of the two optional fields"""
        assert any(
            [values.get("message_type") is not None, values.get("transaction_id") is not None]
        ), "content must contain either a message_type or a transaction_id"
        assert not all(
            [values.get("message_type") is not None, values.get("transaction_id") is not None]
        ), "content must contain either a message_type or transaction_id, not both"
        return values

    class Config:
        """Allows for the callable field type"""

        arbitrary_types_allowed = True


class MinimalErrorSchema(BaseModel):
    """The minimal field definition for an error response"""

    msg_id: UUID
    event: str
    data: Optional[Dict]
    processed_timestamp: datetime
    channel: str


class TopicActionReplyData(BaseModel):
    """The generic response payload for subscription events"""

    success: bool


class KernelStatusUpdate(BaseModel):
    session_id: str
    kernel: KernelDetails
    metadata: Optional[dict] = None

    @property
    def kernel_channel(self):
        """Helper to build kernel channel names for subscriptions"""
        return f"kernels/{self.kernel.id}"


class FileSubscriptionUser(BaseModel):
    """The type information for users actively viewing a shared subscription (e.g. file)"""

    user_id: UUID
    file_id: UUID
    last_event_at: Optional[datetime]
    subscribed: Optional[bool]
    cell_id_selected: Optional[str]


class FileSubscribeActionReplyData(TopicActionReplyData):
    """The response payload for a file subscription event."""

    user_subscriptions: List[FileSubscriptionUser] = Field(default_factory=list)
    deltas_to_apply: List[FileDelta] = Field(default_factory=list)
    cell_states: List[CellStateMessage] = Field(default_factory=list)
    kernel_session: Optional[KernelStatusUpdate] = None
    latest_delta_id: Optional[UUID]


class FileSubscribeRequestData(BaseModel):
    """The payload type information for a file delta catchup payload."""

    # ID of the last delta that the client processed.
    # Will trigger catch up mechanism and return a sorted list of deltas to apply
    from_delta_id: Optional[UUID] = None

    # ID of the document version.
    # Will trigger catch up mechanism and return a sorted list of deltas to apply
    from_version_id: Optional[UUID] = None


class FileSubscribeRequestSchema(GenericRTURequestSchema[FileSubscribeRequestData]):
    """The data schema for a FileSubscription Request"""

    @property
    def last_transaction_id(self) -> Optional[UUID]:
        """Helper to extract last_transaction_id"""
        return getattr(self.data, "last_transaction_id")


FileSubscribeReplySchema = GenericRTUReplySchema[FileSubscribeActionReplyData]


class OutputMessage(BaseModel):
    """The base output message type"""

    raw: Dict


class OutputType(enum.Enum):
    """The type class representing the available types of outputs.

    Generally this is used for rendering purposes, but it mirrors Jupyter protocols.
    """

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    execute_result = enum.auto()
    stream = enum.auto()
    display_data = enum.auto()
    error = enum.auto()
    clear_output = enum.auto()
    update_display_data = enum.auto()


class OutputContent(BaseModel):
    """The type class holding the contents of an output from the parent message type."""

    raw: Optional[str] = None
    url: Optional[str] = None
    mimetype: str

    @root_validator
    def either_raw_or_url(cls, values):
        """Validation to ensure we have content via raw value or a url fetch."""
        assert any(
            [values.get("raw") is not None, values.get("url") is not None]
        ), "content must contain either raw data or a url"
        assert not all(
            [values.get("raw") is not None, values.get("url") is not None]
        ), "content must contain either raw data or url, not both"
        return values


class OutputData(NoteableAPIModel):
    """The type information for specifying a renderable output message."""

    type: OutputType
    display_id: Optional[str]
    available_mimetypes: List[str]
    content_metadata: OutputContent
    content: Optional[OutputContent]
    parent_collection_id: UUID


class CellStateMessageData(BaseModel):
    """
    Pydantic representation of a cell state for front-end

    This is also used as input to CellStateDAO for creation and update
    """

    kernel_session_id: UUID
    cell_id: str
    state: CellState
    execution_count: Optional[int]

    # This is Gate's (cockroach's "now") time at which it recieved an execution request from geas
    queued_at: Optional[datetime]
    # Start and finish times are taken from planar-ally messages (set from planar-ally's time of witnessing)
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_secs: Optional[float]

    queued_by_id: Optional[UUID]  # user ID


class CellStateMessageReply(GenericRTUReplySchema[CellStateMessageData]):
    """Defines a status update message from the rtu websocket"""

    event = 'cell_state_update_event'


class KernelOutputType(enum.Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    execute_result = enum.auto()
    stream = enum.auto()
    display_data = enum.auto()
    error = enum.auto()
    clear_output = enum.auto()
    update_display_data = enum.auto()


class KernelOutputContent(BaseModel):
    raw: Optional[str] = None
    url: Optional[str] = None
    mimetype: str


class KernelOutput(NoteableAPIModel):
    type: KernelOutputType
    display_id: Optional[str]
    available_mimetypes: List[str]
    content_metadata: KernelOutputContent
    content: Optional[KernelOutputContent]
    parent_collection_id: UUID

    class Config:
        arbitrary_types_allowed = True


class KernelOutputCollection(NoteableAPIModel):
    cell_id: Optional[str] = None
    widget_model_id: Optional[str] = None
    file_id: UUID
    outputs: List[KernelOutput]

    @root_validator
    def has_cell_or_model_id(cls, values):
        assert any(
            [values.get("cell_id") is not None, values.get("widget_model_id") is not None]
        ), "collection must contain either cell id or model id"
        assert not all(
            [values.get("cell_id") is not None, values.get("widget_model_id") is not None]
        ), "collection must contain either cell id or model id, not both"
        return values


UpdateOutputCollectionEventSchema = GenericRTUReplySchema[KernelOutputCollection]

AppendOutputEventSchema = GenericRTUReplySchema[KernelOutput]


@enum.unique
class KernelStatus(enum.Enum):
    """The enumerable defining all the possible kernel states one can land in.

    These are super set of the kernel status in Jupyter, as we additionally
    monitor container states before a kernel is available.
    """

    # The kernel has been requested in kubernetes and is being scheduled on an
    # available node. If it's unable to be scheduled then the status will never
    # go to scheduled.
    REQUESTED = "requested"

    # This server instance knows about the kernel and is waiting to request resources
    # from Kubernetes.
    SCHEDULED = "scheduled"

    # In the case of a new node, the docker images will need to be pulled and
    # this state may last longer in those cases.
    PULLING_INIT_RESOURCES = "pulling-initialization-resources"
    # Kernel initialization happens immediately after the docker images are pulled,
    # this step includes pulling project files. The state may cycle between this and
    # pulling-initialization-resources if there are multiple init containers.
    INIT_CONTAINER_STARTED = "init-container-started"

    # After init containers are run, kubernetes will pull docker images for the kernel container and planar-ally.
    PULLING_RUNTIME_RESOURCES = "pulling-runtime-resources"
    # After a runtime container's resources are pulled the container will be started,
    # this state may be sent more than once and cycle between this state and pulling-runtime-resources.
    RUNTIME_CONTAINER_STARTED = "runtime-container-started"

    # The kernel container and planar-ally are starting up but not ready to accept ZMQ connections/requests
    PREPARING = "preparing"

    # After all the kernel containers are created, the launching state is emitted to show that the
    # containers are now starting up but are not ready to accept connections.
    LAUNCHING = "launching"

    # Kernel has accepted a ZMQ connection. Sent by the server to indicate that
    # a kernel is ready for input even if it hasn't sent a status message.
    LAUNCHED = "launched"

    # Kernel has been successfully bootstrapped and we're waiting on the kernel to
    # accept ZMQ connections. This is sent by the kernel while it's preparing its
    # environment.
    STARTING = "starting"

    # Kernel is ready for input.
    IDLE = "idle"

    # Kernel is processing input.
    BUSY = "busy"

    # Kernel has been shutdown and we're waiting on it to restart. Sent by the server
    # to indicate that this process has begun.
    RESTARTING = "restarting"

    # Sent by planar-ally when the kernel restarted because it failed a liveness check,
    # this is commonly sent when the kernel OOMs.
    FORCED_RESTART = "forced-restart"

    # Kernel shutdown has been initiated and is being awaited. Sent
    # server to indicate that a kernel shutdown request is pending.
    SHUTTING_DOWN = "shutting down"

    # Kernel has been shutdown and we're not expecting it to restart. Sent by the
    # server to indicate that a kernel shutdown request was fulfilled.
    SHUTDOWN = "shutdown"

    # Kernel has been shutdown by an outside process. Sent by the server when it
    # attempts to refresh connection data and discovers that the kernel pod no
    # longer exists. Or by the kernel sidecar when a kernel has been idle too long.
    CULLED = "culled"

    # Kernel failed to bootstrap. Sent by the server when we fail to process a kernel
    # start request.
    FAILED = "failed"

    def __str__(self):
        """Helper to make printing pretty"""
        return self.value

    @property
    def kernel_is_in_valid_state(self):
        """Returns whether the state is valid to be used and executed against."""
        return self not in {
            KernelStatus.FAILED,
            KernelStatus.CULLED,
            KernelStatus.RESTARTING,
            KernelStatus.FORCED_RESTART,
        }

    @classmethod
    def not_live_statuses(cls):
        """Statuses of kernel session rows that don't count against a user's current active session count."""
        return {
            KernelStatus.FAILED,
            KernelStatus.CULLED,
            KernelStatus.SHUTDOWN,
            KernelStatus.SHUTTING_DOWN,
        }

    @property
    def kernel_is_alive(self):
        """Returns a boolean about whether the kernel should be expected to respond to requests."""
        return self in {
            KernelStatus.LAUNCHED,
            KernelStatus.STARTING,
            KernelStatus.IDLE,
            KernelStatus.BUSY,
        }


class ProjectFilesSyncedMessage(BaseModel):
    """Defines the message for project file synchronizatoin.

    Currently this just uses BaseModel fields to specify without any additions.
    """

    pass


class AuthenticationRequestData(BaseModel):
    """Defines a request to ping the rtu websocket"""

    token: str


class AuthenticationRequest(GenericRTURequestSchema[AuthenticationRequestData]):
    """Defines a request to authenticate against the rtu websocket.

    This is required due to not all websocket clients being able to send
    bearer tokens in the request payload itself.
    """

    channel: str = 'system'
    event: str = 'authenticate_request'


class AuthenticationReplyData(BaseModel):
    """Defines a response for authentication from the rtu websocket"""

    success: bool
    user: Optional[User] = None


AuthenticationReply = GenericRTUReplySchema[AuthenticationReplyData]


class PingRequest(GenericRTURequest):
    """Defines a request to ping the rtu websocket"""

    channel: str = 'system'
    event: str = 'ping_request'


PingReply = GenericRTUReply


class CellContentsDeltaRequest(GenericRTURequestSchema[CellContentsDeltaRequestDataWrapper]):
    """Defubes the delta request for cell contents replacement over the rtu websocket"""

    event: str = 'new_delta_request'


FileDeltaReply = GenericRTUReplySchema[TopicActionReplyData]

FileDeltaRequestSchema = GenericRTURequestSchema[NewFileDeltaData]


RTU_MESSAGE_TYPES = {
    "append_output_event": GenericRTUReplySchema[OutputData],
    "authenticate_reply": AuthenticationReplyData,
    "authenticate_request": AuthenticationRequest,
    # "create_comment_event"
    # "create_output_event",
    # "v0_create_widget_model_event",
    # "delete_comment_event",
    # "echo_request",
    # "files_synced_event",
    # "new_delta_event",
    "new_delta_request": GenericRTURequestSchema[FileDeltaRequestSchema],
    "new_delta_reply": FileDeltaReply,
    "ping_reply": PingReply,
    "ping_request": PingRequest,
    # "remove_user_file_subscription_event",
    # "resolve_comment_thread_event",
    # "restore_comment_thread_event",
    "subscribe_reply": GenericRTUReplySchema[TopicActionReplyData],
    "subscribe_request": GenericRTURequest,
    # "unsubscribe_request",
    # "cell_state_update_event",
    # "update_comment_event",
    # "update_output_collection_event",
    # "update_output_event",
    # "update_outputs_by_display_id_event",
    # "update_user_cell_selection_request",
    # "update_user_event",
    # "update_user_file_subscription_event",
    # "update_user_request",
    # "v0_update_widget_model_event",
    # "user_message_event",
    # "v0_file_versions_changed_event",
    ## Errors
    ### Drop The Deltas?
    # "delta_rejected",
    ### Retry maybe?
    # "server_error",
    ### Hard Errors. Maybe Just Give up
    # "malformed_request",
    # "channel_does_not_exist",
    # "permission_denied",
    # "unspecified_error",
    # "invalid_event",
    # "invalid_data",
}

RTU_ERROR_HARD_MESSAGE_TYPES = {
    "malformed_request",
    "channel_does_not_exist",
    "permission_denied",
    "unspecified_error",
    "invalid_event",
    "invalid_data",
}
