import os
import uuid
from typing import Optional

from pydantic import validator

from origami.models.api.base import ResourceBase


class Project(ResourceBase):
    name: str
    description: Optional[str]
    space_id: uuid.UUID
    url: Optional[str] = None

    @validator("url", always=True)
    def construct_url(cls, v, values):
        noteable_url = os.environ.get("PUBLIC_NOTEABLE_URL", "https://app.noteable.io")
        return f"{noteable_url}/p/{values['id']}"
