from __future__ import annotations

import json
from uuid import UUID, uuid4
from base64 import decodebytes
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

import orjson
import nbformat
import structlog
from pydantic import BaseModel, Field, root_validator, validator


from ..format import nbformat_writes_fast
from ..pathing import ensure_relative_path
from .access_levels import AccessLevel, Visibility, ResourceData
from .models import Resource
from .deltas import CellContentsDeltaRequestData, FileDeltaType, FileDeltaAction, V2CellContentsProperties


JSON = Dict[str, Any]
logger = structlog.get_logger(__name__)


class FileType(str, Enum):
    """The types of objects found along a path and have first-class noteable support."""

    def _generate_next_value_(name, start, count, last_values):
        return name

    file = auto()
    notebook = auto()

    def file_format(self) -> FileFormat:
        if self is FileType.notebook:
            return FileFormat.json
        return FileFormat.text


class FileFormat(Enum):
    """The representation of file storage formats we explicitly handle"""

    def _generate_next_value_(name, start, count, last_values):
        return name

    json = auto()
    text = auto()
    base64 = auto()

    def to_mimetype(self) -> Optional[str]:
        if self is FileFormat.json:
            return "application/json"
        elif self is FileFormat.text:
            return "text/plain"
        elif self is FileFormat.base64:
            return "application/octet-stream"
        return None

    @classmethod
    def from_api_details(cls, file_format: Optional[FileFormat], file_type: FileType) -> FileFormat:
        """This is a temporary method until the frontend properly sends the file format"""
        if file_format:
            return file_format
        return FileFormat.json if file_type == FileType.notebook else FileFormat.text


class JupyterServerResponse(BaseModel):
    name: str
    path: str
    type: FileType
    writable: bool
    created: datetime
    last_modified: datetime
    size: Optional[int]
    mimetype: Optional[str]
    content: Union[str, List[JupyterServerResponse], JSON, None]
    format: Optional[FileFormat]
    message: Optional[str] = None

    def as_format(self, format: Optional[FileFormat]) -> "JupyterServerResponse":
        if format is FileFormat.text and self.format is not FileFormat.text:
            if self.format is FileFormat.base64 and self.content:
                try:
                    return self.copy(
                        update={
                            "format": FileFormat.text,
                            "content": decodebytes(self.content.encode("utf8")).decode("utf8"),
                        }
                    )
                except ValueError:
                    logger.exception(
                        "unable to convert content to text",
                        path=self.path,
                        format=str(self.format),
                        file_type=str(self.type),
                        mimetype=str(self.mimetype),
                    )
            elif self.format is FileFormat.json and self.content:
                try:
                    return self.copy(
                        update={
                            "format": FileFormat.text,
                            "content": json.dumps(self.content),
                        }
                    )
                except ValueError:
                    logger.exception(
                        "unable to convert content to json",
                        path=self.path,
                        format=str(self.format),
                        file_type=str(self.type),
                        mimetype=str(self.mimetype),
                    )

        return self


JupyterServerResponse.update_forward_refs()


class UserAndRole(BaseModel):
    user_id: UUID
    access_level: AccessLevel
    # role is deprecated in favor of access_level
    role: AccessLevel = None

    @root_validator()
    def validate_model(cls, values):
        values["role"] = values["access_level"]
        return values

    class Config:
        orm_mode = True


class FileRBACModel(BaseModel):
    rbac: Optional[ResourceData]
    users: Optional[List[UserAndRole]]
    # A dictionary returning the number of users granted access on the parent resources, if any
    parent_resource_users: Dict[Resource, int] = Field(default_factory=dict)


class V1File(FileRBACModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    upload_completed_at: Optional[datetime]
    project_id: UUID
    filename: str
    path: str
    type: FileType
    format: Optional[FileFormat]
    mimetype: Optional[str] = None
    size: Optional[int] = None
    kernel_filesystem_path: Optional[str]
    created_by_id: UUID
    visibility: Visibility
    visibility_default_access_level: Optional[AccessLevel]
    source_file_id: Optional[UUID]
    is_playground_mode_file: bool
    space_id: UUID
    project_user_access_level: Optional[AccessLevel]
    space_user_access_level: Optional[AccessLevel]
    last_save_delta_id: Optional[UUID]
    file_store_path: str
    current_version_id: Optional[UUID] = None

    # Only set when creating a new file or updating an existing file.
    presigned_upload_url_info: Optional[Any] = None
    # Only set when fetching the file through /api/v1/files/:id route.
    presigned_download_url: Optional[str] = None

    @validator("kernel_filesystem_path", pre=True, always=True)
    def validate_kernel_filesystem_path(cls, kernel_filesystem_path, values):
        return values["path"]

class File(V1File):
    content: Optional[Union[str, JSON]] = None
    content_truncated: bool = False

    @property
    def json_contents(self):
        if self.content is None:
            raise ValueError("Contents of file object are missing, cannot request values served from contents")
        elif isinstance(self.content, str):
            return orjson.loads(self.content)
        else:
            return self.content

    def as_jupyter_server_response(
        self, as_format: Optional[FileFormat] = None
    ) -> JupyterServerResponse:
        """Converts the Noteable File API response model into the original
        Jupyter Server response model. Allows us to use our existing proprietary
        data layer, while supporting the existing ecosystem.

        as_format can be specified to convert the current file format into another file format.
        """
        return JupyterServerResponse(
            name=self.filename,
            path=self.path,
            type=self.type,
            writable=True,
            created=self.created_at,
            last_modified=self.updated_at,
            size=self.size,
            mimetype=self.mimetype,
            content=self.content,
            format=self.format,
            message=None,
        ).as_format(as_format)

    @property
    def channel(self):
        """Helper to build file channel names from file ids"""
        return f"files/{self.id}"

    def generate_delta_request(self, transaction_id: UUID, delta_type: FileDeltaType, delta_action: FileDeltaAction, cell_id: Optional[UUID], properties: V2CellContentsProperties):
        # Avoid circular import
        from .rtu import CellContentsDeltaRequest

        data = CellContentsDeltaRequestData(
            id=uuid4(),
            delta_type=delta_type,
            delta_action=delta_action,
            resource_id=cell_id,
            properties=properties
        )
        return CellContentsDeltaRequest(
            data=data,
            transaction_id=transaction_id,
            channel=self.channel
        )


class FilePutDetails(BaseModel):
    path: str
    type: FileType
    project_id: UUID
    format: FileFormat
    content: Union[str, JSON]

    @validator("path")
    def validate_path(cls, path, values):
        return ensure_relative_path(path)

    @validator("format")
    def format_type_pinning(cls, format, values):
        if values["type"] is FileType.notebook and format is not FileFormat.json:
            raise ValueError("Notebooks only support JSON format")
        return format

    @validator("content")
    def validate_content(cls, content, values):
        # When we do a V1 files API we should do something a little more obvious.

        if values['type'] is FileType.notebook:
            if not content:
                content = nbformat.v4.new_notebook()
                content.cells.append(nbformat.v4.new_code_cell())
            try:
                # coerce into NotebookNode
                if isinstance(content, str):
                    content = nbformat.reads(content, nbformat.NO_CONVERT)
                else:
                    content = nbformat.from_dict(content)
            except Exception:
                logger.exception("Exception encountered while validating notebook content")
                raise

        return content


class FilePatch(FilePutDetails):
    project_id: Optional[UUID]
    path: Optional[str]
    type: Optional[FileType]
    format: Optional[FileFormat]
    content: Union[str, JSON, None]


class PutResult(BaseModel):
    file: File


class CopyDetails(BaseModel):
    # path is where to copy the file to
    path: str
    # specifying a new project_id allows copying between projects
    project_id: UUID
    # include users with explicit permission on the original file
    # to have permission on the newly copied file
    include_shared_users: bool = False
    # include comments from the original file in the newly created file
    include_comments: bool = False

    @validator("path")
    def validate_path(cls, path, values):
        return ensure_relative_path(path)


class RenameDetails(BaseModel):
    # the new path to rename the file to
    path: str


class CopyResult(BaseModel):
    file: File


class DeleteResult(BaseModel):
    file_id: UUID


class TreeResult(BaseModel):
    prefix: str
    folder_name: str
    children: List[File]


class ExistsResult(BaseModel):
    exists: bool
