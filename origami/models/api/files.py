import os
import pathlib
import uuid
from typing import Literal, Optional

from pydantic import model_validator

from origami.models.api.base import ResourceBase


class File(ResourceBase):
    filename: str
    path: pathlib.Path
    project_id: uuid.UUID
    space_id: uuid.UUID
    size: Optional[int] = None
    mimetype: Optional[str] = None
    type: Literal["file", "notebook"]
    current_version_id: Optional[uuid.UUID] = None
    # presigned_download_url is None when listing Files in a Project, need to hit /api/v1/files/{id}
    # to get it. Use presigned download url to get File content including Notebooks
    presigned_download_url: Optional[str] = None
    url: Optional[str] = None

    # XXX write test
    @model_validator(mode="after")
    def construct_url(self):
        noteable_url = os.environ.get("PUBLIC_NOTEABLE_URL", "https://app.noteable.io")
        self.url = f"{noteable_url}/f/{self.id}/{self.path}"

        return self


class FileVersion(ResourceBase):
    created_by_id: Optional[uuid.UUID] = None
    number: int
    name: Optional[str] = None
    description: Optional[str] = None
    file_id: uuid.UUID
    project_id: uuid.UUID
    space_id: uuid.UUID
    content_presigned_url: str
