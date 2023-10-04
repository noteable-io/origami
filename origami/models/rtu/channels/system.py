"""
The primary purpose of the system channel is authenticating an RTU session after the websocket
connection has been established. There are a number of debug-related RTU events on this channel
as well.

1. authenticate_request - pass in a JWT to authenticate the rest of the RTU session so that events
   on channels like files and projects, which require RBAC checks, have a User account to check
2. ping_request and ping_reply - used to test RTU connection
3. whoami_request and whoami_reply - used to get the User account associated with the RTU session
   (also returned as part of the payload on the authenticate_reply event though)
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from origami.models.api.users import User
from origami.models.rtu.base import BaseRTURequest, BaseRTUResponse


class SystemRequest(BaseRTURequest):
    channel: str = "system"
    channel_prefix: Literal["system"] = "system"


class SystemResponse(BaseRTUResponse):
    channel: str = "system"
    channel_prefix: Literal["system"] = "system"


# The first thing RTU Clients should do after websocket connection is authenticate with a JWT,
# same access token as what is included in Authorization bearer headers for API requests
class AuthenticateRequestData(BaseModel):
    token: str
    rtu_client_type: str = "origami"


class AuthenticateRequest(SystemRequest):
    event: Literal["authenticate_request"] = "authenticate_request"
    data: AuthenticateRequestData


class AuthenticateReplyData(BaseModel):
    success: bool
    user: User


class AuthenticateReply(SystemResponse):
    event: Literal["authenticate_reply"] = "authenticate_reply"
    data: AuthenticateReplyData


# Below is all mainly used for debug, App devs don't need to do anything with these usually
class PingRequest(SystemRequest):
    event: Literal["ping_request"] = "ping_request"


class PingResponse(SystemResponse):
    event: Literal["ping_response"] = "ping_response"


class WhoAmIRequest(SystemRequest):
    event: Literal["whoami_request"] = "whoami_request"


class WhoAmIResponseData(BaseModel):
    user: Optional[User]  # is None if RTU session isn't authenticated


class WhoAmIResponse(SystemResponse):
    event: Literal["whoami_response"] = "whoami_response"
    data: WhoAmIResponseData


SystemRequests = Annotated[
    Union[
        AuthenticateRequest,
        PingRequest,
        WhoAmIRequest,
    ],
    Field(discriminator="event"),
]
SystemResponses = Annotated[
    Union[
        AuthenticateReply,
        PingResponse,
        WhoAmIResponse,
    ],
    Field(discriminator="event"),
]
