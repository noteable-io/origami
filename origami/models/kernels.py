import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class KernelDetails(BaseModel):
    name: str
    last_activity: Optional[datetime] = None
    execution_state: str


class KernelStatusUpdate(BaseModel):
    session_id: uuid.UUID
    kernel: KernelDetails


class CellState(BaseModel):
    cell_id: str
    state: str


class KernelSession(BaseModel):
    id: uuid.UUID
    kernel: KernelDetails
