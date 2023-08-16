import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, root_validator


class BooleanReplyData(BaseModel):
    # Gate will reply to most RTU requests with an RTU reply that's just success=True/False
    success: bool


class BaseRTURequest(BaseModel):
    transaction_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    channel: str
    channel_prefix: Optional[str]  # override in Channels base classes to be Literal
    event: str  # override in Events subclasses to be Literal
    data: Any = None  # override in subclasses to be a pydantic model

    class Config:
        # do not include channel_prefix when serializing to dict / json
        fields = {'channel_prefix': {'exclude': True}}

    @root_validator
    def set_channel_prefix(cls, values):
        values['channel_prefix'] = values['channel'].split('/')[0]
        return values


class BaseRTUResponse(BaseModel):
    transaction_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    channel: str
    channel_prefix: Optional[str]  # override in Channels base classes to be Literal
    event: str  # override in Events subclasses to be Literal
    data: Any = None  # override in subclasses to be a pydantic model
    executing_user_id: Optional[uuid.UUID] = None
    processed_timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # do not include channel_prefix when serializing to dict / json
        fields = {'channel_prefix': {'exclude': True}}

    @root_validator
    def set_channel_prefix(cls, values):
        values['channel_prefix'] = values['channel'].split('/')[0]
        return values
