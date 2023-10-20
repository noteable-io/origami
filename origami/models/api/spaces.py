import os
from typing import Optional

from pydantic import model_validator

from origami.models.api.base import ResourceBase


class Space(ResourceBase):
    name: str
    description: Optional[str] = None
    url: Optional[str] = None

    @model_validator(mode="after")
    def construct_url(self):
        noteable_url = os.environ.get("PUBLIC_NOTEABLE_URL", "https://app.noteable.io")
        self.url = f"{noteable_url}/s/{self.id}"

        return self
