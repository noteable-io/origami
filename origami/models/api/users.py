import uuid
from typing import Optional

from pydantic import model_validator

from origami.models.api.base import ResourceBase


class User(ResourceBase):
    """The user fields sent to/from the server"""

    handle: str
    email: Optional[str] = None  # not returned if looking up user other than yourself
    first_name: str
    last_name: str
    origamist_default_project_id: Optional[uuid.UUID] = None
    principal_sub: Optional[str] = None  # from /users/me only, represents auth type
    auth_type: Optional[str] = None

    @model_validator(mode="after")
    def construct_auth_type(self):
        if self.principal_sub:
            self.auth_type = self.principal_sub.split("|")[0]

        return self
