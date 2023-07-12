import os
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, validator


class ResourceBase(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


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


class Space(ResourceBase):
    name: str
    description: Optional[str]
    url: Optional[str] = None

    @validator("url", always=True)
    def construct_url(cls, v, values):
        noteable_url = os.environ.get('PUBLIC_NOTEABLE_URL', 'https://app.noteable.io')
        return f"{noteable_url}/s/{values['id']}"


class Project(ResourceBase):
    name: str
    description: Optional[str]
    space_id: uuid.UUID
    url: Optional[str] = None

    @validator("url", always=True)
    def construct_url(cls, v, values):
        noteable_url = os.environ.get('PUBLIC_NOTEABLE_URL', 'https://app.noteable.io')
        return f"{noteable_url}/p/{values['id']}"


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


class KernelOutputContent(BaseModel):
    raw: Optional[str] = None
    url: Optional[str] = None
    mimetype: str


class KernelOutput(ResourceBase):
    type: str
    display_id: Optional[str]
    available_mimetypes: List[str]
    content_metadata: KernelOutputContent
    content: Optional[KernelOutputContent]
    parent_collection_id: uuid.UUID


class KernelOutputCollection(ResourceBase):
    cell_id: Optional[str] = None
    widget_model_id: Optional[str] = None
    file_id: uuid.UUID
    outputs: List[KernelOutput]
