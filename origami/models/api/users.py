import uuid
from typing import Optional

from pydantic import validator

from origami.models.api.base import ResourceBase


class User(ResourceBase):
    """The user fields sent to/from the server"""

    handle: str
    email: Optional[str]  # not returned if looking up user other than yourself
    first_name: str
    last_name: str
    origamist_default_project_id: Optional[uuid.UUID]
    principal_sub: Optional[str]  # from /users/me only, represents auth type
    auth_type: Optional[str]

    @validator("auth_type", always=True)
    def construct_auth_type(cls, v, values):
        if values.get('principal_sub'):
            return values["principal_sub"].split("|")[0]
