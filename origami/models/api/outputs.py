import uuid
from typing import List, Optional

from pydantic import BaseModel

from origami.models.api.base import ResourceBase


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
