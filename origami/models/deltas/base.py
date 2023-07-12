import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

NULL_RESOURCE_SENTINEL = "__NULL_RESOURCE__"


class FileDeltaBase(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    file_id: uuid.UUID
    delta_type: str
    delta_action: str
    resource_id: str = NULL_RESOURCE_SENTINEL
    parent_delta_id: Optional[uuid.UUID] = None
    properties: Any = None  # override in subclasses
    # created_at and created_by_id should not be filled out when creating new Delta requests.
    # they are filled out by the server when the Delta is written to the database (with user info
    # coming from the initial authenticate on the RTU session)
    created_at: Optional[datetime] = None
    created_by_id: Optional[uuid.UUID] = None
