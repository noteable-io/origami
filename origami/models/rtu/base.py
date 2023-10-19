import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Annotated


class BooleanReplyData(BaseModel):
    # Gate will reply to most RTU requests with an RTU reply that's just success=True/False
    success: bool


class ChannelPrefixable(BaseModel):
    channel: str
    channel_prefix: Annotated[
        Optional[str], Field(exclude=True)
    ] = None  # override in Channels base classes to be Literal

    @model_validator(mode="after")
    def set_channel_prefix(self):
        self.channel_prefix = self.channel.split("/")[0]
        return self


class BaseRTURequest(ChannelPrefixable):
    transaction_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event: str  # override in Events subclasses to be Literal
    data: Any = None  # override in subclasses to be a pydantic model

    # XXX write tests over set_channel_prefix


class BaseRTUResponse(ChannelPrefixable):
    transaction_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event: str  # override in Events subclasses to be Literal
    data: Any = None  # override in subclasses to be a pydantic model
    executing_user_id: Optional[uuid.UUID] = None
    processed_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # XXX write tests over set_channel_prefix
