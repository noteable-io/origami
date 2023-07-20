import os
import uuid
from typing import Literal, Optional

from pydantic import validator

from origami.models.api.base import ResourceBase


class File(ResourceBase):
    filename: str
    path: str
    project_id: uuid.UUID
    space_id: uuid.UUID
    size: Optional[int]
    type: Literal['file', 'notebook']
    current_version_id: Optional[uuid.UUID]
    # presigned_download_url is None when listing Files in a Project, need to hit /api/v1/files/{id}
    # to get it. Use presigned download url to get File content including Notebooks
    presigned_download_url: Optional[str]
    url: Optional[str] = None

    @validator("url", always=True)
    def construct_url(cls, v, values):
        noteable_url = os.environ.get('PUBLIC_NOTEABLE_URL', 'https://app.noteable.io')
        return f"{noteable_url}/f/{values['id']}"
