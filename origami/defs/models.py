"""This file holds the base models for interpreting or making requests from Noteable
API servers and websockets.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, validator


class NoteableAPIModel(BaseModel):
    """Noteable's Base Data Model

    Contains common fields for all Noteable models, such as id and datetime fields.
    """

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class User(NoteableAPIModel):
    """The user fields sent to/from the server"""

    handle: str
    first_name: str
    last_name: str
    origamist_default_project_id: Optional[uuid.UUID]
    email: Optional[str]  # not returned if lookig up user other than yourself
    principal_sub: Optional[str]  # from /users/me only, represents auth type
    auth_type: Optional[str]

    @validator("auth_type", always=True)
    def construct_auth_type(cls, v, values):
        if values.get('principal_id'):
            return values["principal_sub"].split("|")[0]


@enum.unique
class Resource(enum.Enum):
    """The abstraction of a noteable resource that can have relations and RBAC assignments against it"""

    def _generate_next_value_(name, start, count, last_values):
        return name

    organizations = enum.auto()
    users = enum.auto()

    spaces = enum.auto()
    projects = enum.auto()
    files = enum.auto()
    datasets = enum.auto()
    dataset_files = enum.auto()
    comments = enum.auto()
    kernel_sessions = enum.auto()
