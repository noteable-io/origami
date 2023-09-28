"""
There are six events on the files/<file-id> channel:

1. subscribe_request and subscribe_reply
2. unsubscribe_request and unsubscribe_reply
3. new_delta_request and new_delta_reply (direct) / new_delta_event (broadcast)
 - RTU Errors for invalid_data or permission_denied
4. update_user_cell_selection_request and
   update_user_cell_selection_reply -> update_user_file_subscription_event
5. input_reply_request and input_reply_reply
6. transform_view_to_code_request and transform_view_to_code_reply (DEX export to code cell)
 - The follow on "event" is a new delta event
"""
import uuid
from datetime import datetime
from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError, root_validator

from origami.models.api.outputs import KernelOutput
from origami.models.deltas.discriminators import FileDelta
from origami.models.kernels import CellState, KernelStatusUpdate
from origami.models.rtu.base import BaseRTURequest, BaseRTUResponse, BooleanReplyData


class FilesRequest(BaseRTURequest):
    channel_prefix: Literal['files'] = 'files'


class FilesResponse(BaseRTUResponse):
    channel_prefix: Literal['files'] = 'files'


# When an RTU Client wants to get document model updates from a Notebook, it subscribes to the files
# channel with that Notebook ID.
class FileSubscribeRequestData(BaseModel):
    # One of these two must be set
    from_version_id: Optional[uuid.UUID] = None
    from_delta_id: Optional[uuid.UUID] = None

    class Config:
        exclude_none = True

    @root_validator
    def exactly_one_field(cls, values):
        # Count how many fields are set (i.e., are not None)
        num_set_fields = sum(value is not None for value in values.values())

        # If exactly one field is set, return the values as they are
        if num_set_fields == 1:
            return values

        # If not, raise a validation error
        raise ValidationError('Exactly one field must be set')


class FileSubscribeRequest(FilesRequest):
    event: Literal['subscribe_request'] = 'subscribe_request'
    data: FileSubscribeRequestData


# File subscribe reply has several pieces of information
# - List of deltas to squash into the NotebookBuilder immediately
class FileSubscribeReplyData(BaseModel):
    deltas_to_apply: List[FileDelta]
    latest_delta_id: uuid.UUID
    kernel_session: Optional[KernelStatusUpdate]  # null if no active Kernel for the File
    cell_states: List[CellState]
    # TODO: user_subscriptions


class FileSubscribeReply(FilesResponse):
    event: Literal['subscribe_reply'] = 'subscribe_reply'
    data: FileSubscribeReplyData


# Clients typically do not need to unsubscribe, they can just close the websocket connection
class FileUnsubscribeRequest(FilesRequest):
    event: Literal['unsubscribe_request'] = 'unsubscribe_request'


class FileUnsubscribeReply(FilesResponse):
    event: Literal['unsubscribe_reply'] = 'unsubscribe_reply'
    data: BooleanReplyData


# Deltas are requests to change a document content or perform cell execution. The API server ensures
# they are applied in a linear order, and will return a delta reply if it has been successfully
# recorded, followed by a new delta event propogated to all connected clients.
class NewDeltaRequestData(BaseModel):
    delta: FileDelta
    # When is this second field used?
    output_collection_id_to_copy: Optional[uuid.UUID] = None


class NewDeltaRequest(FilesRequest):
    event: Literal['new_delta_request'] = 'new_delta_request'
    data: NewDeltaRequestData


class NewDeltaReply(FilesResponse):
    event: Literal['new_delta_reply'] = 'new_delta_reply'
    data: BooleanReplyData


class NewDeltaEvent(FilesResponse):
    event: Literal['new_delta_event'] = 'new_delta_event'
    data: FileDelta


# When Cells complete and there's output, a new CellOutputCollectionReplace Delta will come through
# that is a container for multi-part output or a link to a pre-signed download url for large output
# like an image/gif.
class UpdateOutputCollectionEventData(BaseModel):
    pass


class UpdateOutputCollectionEvent(FilesResponse):
    event: Literal['update_output_collection_event'] = 'update_output_collection_event'
    data: UpdateOutputCollectionEventData


# If Cells are streaming multiple outputs like a pip install or for loop and print, then we'll get
# append to output events
class AppendOutputEvent(FilesResponse):
    event: Literal['append_output_event'] = 'append_output_event'
    data: KernelOutput


# User cell selection is a collaboration feature, shows which cell each user is currently editing
# Like Deltas, it follows a request -> reply -> event pattern
class UpdateUserCellSelectionRequestData(BaseModel):
    id: uuid.UUID


class UpdateUserCellSelectionRequest(FilesRequest):
    event: Literal['update_user_cell_selection_request'] = 'update_user_cell_selection_request'
    data: UpdateUserCellSelectionRequestData


class UpdateUserCellSelectionReply(FilesResponse):
    event: Literal['update_user_cell_selection_reply'] = 'update_user_cell_selection_reply'
    data: BooleanReplyData


class UpdateUserFileSubscriptionEventData(BaseModel):
    cell_id_selected: Optional[str]
    file_id: uuid.UUID
    last_event_at: datetime
    subscribed: bool
    user_id: uuid.UUID


class UpdateUserFileSubscriptionEvent(FilesResponse):
    event: Literal['update_user_file_subscription_event'] = 'update_user_file_subscription_event'
    data: UpdateUserFileSubscriptionEventData


class RemoveUserFileSubscriptionEventData(BaseModel):
    user_id: uuid.UUID


class RemoveUserFileSubscriptionEvent(FilesResponse):
    event: Literal['remove_user_file_subscription_event'] = 'remove_user_file_subscription_event'
    data: RemoveUserFileSubscriptionEventData


# CPU / Memory usage metrics reported via k8s
class UsageMetricsEventData(BaseModel):
    cpu_usage_percent: int
    memory_usage_percent: int


class UsageMetricsEvent(FilesResponse):
    event: Literal['usage_metrics_event'] = 'usage_metrics_event'
    data: UsageMetricsEventData


# Transform view to code is a DEX feature, it allows a user to create a new code cell that has
# Python syntax to filter a Dataframe the same way as the current DEX grid view
class TransformViewToCodeRequestData(BaseModel):
    # TODO: Shoup review this
    cell_id: str
    filters: Any
    ignore_index: bool = True
    overrides: dict = Field(default_factory=dict)
    target_cell_type: str = 'code'
    variable_name: str = 'df'


class TransformViewToCodeRequest(FilesRequest):
    event: Literal['transform_view_to_code_request'] = 'transform_view_to_code_request'
    data: TransformViewToCodeRequestData


class TransformViewToCodeReply(FilesResponse):
    event: Literal['transform_view_to_code_reply'] = 'transform_view_to_code_reply'
    data: BooleanReplyData


# When the API squashes Deltas, it will emit a new file versions changed event
class FileVersionsChangedEvent(FilesResponse):
    event: Literal['v0_file_versions_changed_event'] = 'v0_file_versions_changed_event'
    data: Optional[dict]


FileRequests = Annotated[
    Union[
        FileSubscribeRequest,
        FileUnsubscribeRequest,
        NewDeltaRequest,
        UpdateUserCellSelectionRequest,
        TransformViewToCodeRequest,
    ],
    Field(discriminator='event'),
]

FileResponses = Annotated[
    Union[
        FileSubscribeReply,
        FileUnsubscribeReply,
        FileVersionsChangedEvent,
        NewDeltaReply,
        NewDeltaEvent,
        RemoveUserFileSubscriptionEvent,
        TransformViewToCodeReply,
        UpdateUserCellSelectionReply,
        UpdateUserFileSubscriptionEvent,
        UpdateOutputCollectionEvent,
        AppendOutputEvent,
        UsageMetricsEvent,
    ],
    Field(discriminator='event'),
]
