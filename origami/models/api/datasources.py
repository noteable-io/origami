import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DataSource(BaseModel):
    datasource_id: uuid.UUID
    name: str
    description: str
    type_id: str  # e.g. duckdb, postgresql
    sql_cell_handle: str  # this goes in cell metadata for SQL cells
    # One of these three will be not None, and that tells you the scope of the datasource
    space_id: Optional[uuid.UUID]
    project_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_introspectable: bool
    is_legacy: bool
    usability: str
