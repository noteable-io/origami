import os
from typing import Optional

from pydantic import validator

from origami.models.api.base import ResourceBase


class Space(ResourceBase):
    name: str
    description: Optional[str]
    url: Optional[str] = None

    @validator("url", always=True)
    def construct_url(cls, v, values):
        noteable_url = os.environ.get('PUBLIC_NOTEABLE_URL', 'https://app.noteable.io')
        return f"{noteable_url}/s/{values['id']}"
