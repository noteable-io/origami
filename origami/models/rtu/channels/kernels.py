"""
The kernels channel in RTU is primarily used for runtime updates like kernel and cell status,
variable explorer, and outputs vice document model changes on the files channel (adding cells,
updating content, etc)
"""
import uuid
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from origami.models.rtu.base import BaseRTURequest, BaseRTUResponse
from origami.models.runtime import CellState, KernelStatusUpdate


class KernelsRequest(BaseRTURequest):
    channel_prefix: Literal['kernels'] = 'kernels'


class KernelsResponse(BaseRTUResponse):
    channel_prefix: Literal['kernels'] = 'kernels'


class KernelSubscribeRequestData(BaseModel):
    file_id: uuid.UUID


class KernelSubscribeRequest(KernelsRequest):
    event: Literal['subscribe_request'] = 'subscribe_request'
    data: KernelSubscribeRequestData


# Kernel status is returned on subscribe and also updated through kernel status updates
class KernelSubscribeReplyData(BaseModel):
    success: bool
    kernel_session: Optional[KernelStatusUpdate]  # None if no Kernel is alive for a file


class KernelSubscribeReply(KernelsResponse):
    event: Literal['subscribe_reply'] = 'subscribe_reply'
    data: KernelSubscribeReplyData


class KernelStatusUpdateResponse(KernelsResponse):
    event: Literal['kernel_status_update_event'] = 'kernel_status_update_event'
    data: KernelStatusUpdate


# Cell State
class BulkCellStateUpdateData(BaseModel):
    cell_states: List[CellState]


class BulkCellStateUpdateResponse(KernelsResponse):
    event: Literal['bulk_cell_state_update_event'] = 'bulk_cell_state_update_event'
    data: BulkCellStateUpdateData


# Variable explorer updates return a list of current variables in the kernel
# On connect to a new Kernel, Clients can send a request to trigger an event. Otherwise events occur
# after cell execution automatically.
class VariableExplorerUpdateRequest(KernelsRequest):
    event: Literal['variable_explorer_update_request'] = 'variable_explorer_update_request'


class VariableExplorerResponse(KernelsResponse):
    event: Literal['variable_explorer_event'] = 'variable_explorer_event'


KernelRequests = Annotated[
    Union[KernelSubscribeRequest, VariableExplorerUpdateRequest], Field(discriminator="event")
]

KernelResponses = Annotated[
    Union[
        KernelSubscribeReply,
        KernelStatusUpdateResponse,
        BulkCellStateUpdateResponse,
        VariableExplorerResponse,
    ],
    Field(discriminator="event"),
]
