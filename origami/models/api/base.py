import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResourceBase(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
