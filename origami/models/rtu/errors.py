from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from origami.models.rtu.base import BaseRTUResponse


class ErrorData(BaseModel):
    message: str


# Error when we send over a request that doesn't match any handlers
class InvalidEvent(BaseRTUResponse):
    event: Literal['invalid_event'] = 'invalid_event'
    data: ErrorData


# Error when the payload of our request has a validation error
class InvalidData(BaseRTUResponse):
    event: Literal['invalid_data'] = 'invalid_data'
    data: ErrorData


# Error when RTU session isn't authenticated or the request does not pass RBAC checks
class PermissionDenied(BaseRTUResponse):
    event: Literal['permission_denied'] = 'permission_denied'
    data: ErrorData


class InconsistentStateEvent(BaseRTUResponse):
    event: Literal['inconsistent_state_event'] = 'inconsistent_state_event'
    data: ErrorData


RTUError = Annotated[
    Union[
        InvalidEvent,
        InvalidData,
        PermissionDenied,
        InconsistentStateEvent,
    ],
    Field(discriminator="event"),
]
