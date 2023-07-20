import os
import pathlib
import uuid
from typing import Literal, Optional

from pydantic import validator

from origami.models.api.base import ResourceBase


class File(ResourceBase):
    filename: str
    path: pathlib.Path
    project_id: uuid.UUID
    space_id: uuid.UUID
    size: Optional[int] = None
    mimetype: Optional[str] = None
    type: Literal['file', 'notebook']
    current_version_id: Optional[uuid.UUID] = None
    # presigned_download_url is None when listing Files in a Project, need to hit /api/v1/files/{id}
    # to get it. Use presigned download url to get File content including Notebooks
    presigned_download_url: Optional[str] = None
    url: Optional[str] = None

    @validator("url", always=True)
    def construct_url(cls, v, values):
        noteable_url = os.environ.get('PUBLIC_NOTEABLE_URL', 'https://app.noteable.io')
        return f"{noteable_url}/f/{values['id']}/{values['path']}"
