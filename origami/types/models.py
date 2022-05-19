"""This file holds the base models for interpreting or making requests from Noteable
API servers and websockets.
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class NoteableAPIModel(BaseModel):
    """Noteable's Base Data Model

    Contains common fields for all Noteable models, such as id and datetime fields.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class GlobalRole(enum.Enum):
    """The overall user role options within Noteable"""

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    super_admin = enum.auto()
    user = enum.auto()


class User(NoteableAPIModel):
    """The user fields sent to/from the server"""

    first_name: str
    last_name: str
    # Omitted on requests
    email: Optional[str]
    principal_id: str
    active: bool
    global_role: GlobalRole


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
