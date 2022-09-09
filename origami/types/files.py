"""This file serves to capture the NotebookFile abstraction and its model interaction with Noteable."""

from __future__ import annotations

import json
from base64 import decodebytes
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

import nbformat
import orjson
import structlog
from pydantic import BaseModel, Field, root_validator, validator

from ..pathing import ensure_relative_path
from .access_levels import AccessLevel, ResourceData, Visibility
from .deltas import FileDeltaAction, FileDeltaRequestBase, FileDeltaType, NewFileDeltaData
from .models import Resource

JSON = Dict[str, Any]
logger = structlog.get_logger(__name__)


class FileType(str, Enum):
    """The types of objects found along a path and have first-class noteable support."""

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    file = auto()
    notebook = auto()

    def file_format(self) -> FileFormat:
        """Helper to define file format based on file type"""
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
        """Mimetype generator based on file type"""
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
    """This is a model converting the Noteable responses into standard Jupyter REST responses for
    file contents. This is really helpful in making a bridge to other OSS libraries that speak
    Jupyter syntax since the ipynbs are valid Jupyter files, but with some permissions and metadata
    above the standard abstraction.
    """

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
        """Formats the file contents into text, json, or base64 as is often used in Jupyter servers."""
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


JupyterServerResponse.update_forward_refs()  # Gets type refs correctly updated


class UserAndRole(BaseModel):
    """The model holding a user and their given permissions for a resource"""

    user_id: UUID
    access_level: AccessLevel
    # role is deprecated in favor of access_level
    role: AccessLevel = None

    @root_validator()
    def validate_model(cls, values):
        """Ensures that the role and access_level match for backwards compatibility"""
        values["role"] = values["access_level"]
        return values


class FileRBACModel(BaseModel):
    """The representation of an role based permission specification for any resource in Noteable"""

    rbac: Optional[ResourceData]
    users: Optional[List[UserAndRole]]
    # A dictionary returning the number of users granted access on the parent resources, if any
    parent_resource_users: Dict[Resource, int] = Field(default_factory=dict)


class NotebookFile(FileRBACModel):
    """The file model representing a Notebook file in Noteable. This is the response model from get
    requests against the REST APIs and holds details needed for coordinated real time updates.
    """

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

    content: Optional[Union[str, JSON]] = None
    content_truncated: bool = False

    @validator("kernel_filesystem_path", pre=True, always=True)
    def validate_kernel_filesystem_path(cls, kernel_filesystem_path, values):
        """Confirms that there is a path subkey for the 'kernel_filesystem_path'"""
        return values["path"]

    # TODO: Memoize?
    @property
    def json_contents(self):
        """Loads contents into JSON dicts if it's still in a string representation."""
        if self.content is None:
            raise ValueError(
                "Contents of file object are missing, cannot request values served from contents"
            )
        elif isinstance(self.content, str):
            return orjson.loads(self.content)
        else:
            return self.content

    def as_jupyter_server_response(
        self, as_format: Optional[FileFormat] = None
    ) -> JupyterServerResponse:
        """Converts the Noteable NotebookFile API response model into the original
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

    def generate_delta_request(
        self,
        transaction_id: UUID,
        delta_type: FileDeltaType,
        delta_action: FileDeltaAction,
        cell_id: Optional[str],
        properties: Any = None,
    ):
        """A helper method for creating delta requests from a NotebookFile object.
        This handles mapping the channel and cell ids to the appropriate requst fields.
        """
        # Avoid circular import
        from .rtu import FileDeltaRequestSchema

        data = NewFileDeltaData(
            delta=FileDeltaRequestBase(
                id=uuid4(),
                delta_type=delta_type,
                delta_action=delta_action,
                resource_id=cell_id,
                properties=properties,
            )
        )
        return FileDeltaRequestSchema(
            data=data,
            transaction_id=transaction_id,
            channel=self.channel,
            event="new_delta_request",
        )


class FilePutDetails(BaseModel):
    """The request payload for file replacement requests"""

    path: str
    type: FileType
    project_id: UUID
    format: FileFormat
    content: Union[str, JSON]

    @validator("path")
    def validate_path(cls, path, values):
        """Ensure that paths are relative for project placement"""
        return ensure_relative_path(path)

    @validator("format")
    def format_type_pinning(cls, format, values):
        """Ensure that notebook files are JSON format"""
        if values["type"] is FileType.notebook and format is not FileFormat.json:
            raise ValueError("Notebooks only support JSON format")
        return format

    @validator("content")
    def validate_content(cls, content, values):
        """Confirms that the notebook content is of the proper shape and type.
        This method also ensures that contents has at least one cell if no content is initially present.
        """
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
    """The request payload for file change requests"""

    project_id: Optional[UUID]
    path: Optional[str]
    type: Optional[FileType]
    format: Optional[FileFormat]
    content: Union[str, JSON, None]


class PutResult(BaseModel):
    """The result payload for file push requests"""

    file: NotebookFile


class CopyDetails(BaseModel):
    """The request payload for file copy requests"""

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
        """Ensure that paths are relative for project placement"""
        return ensure_relative_path(path)


class RenameDetails(BaseModel):
    """The request payload for file name requests"""

    # the new path to rename the file to
    path: str


class CopyResult(BaseModel):
    """The response payload for file copy requests"""

    file: NotebookFile


class FileDeleteResult(BaseModel):
    """The response payload for file deletion requests"""

    file_id: UUID


class TreeResult(BaseModel):
    """The response payload for file tree requests"""

    prefix: str
    folder_name: str
    children: List[NotebookFile]


class ExistsResult(BaseModel):
    """The response payload for existence check requests"""

    exists: bool


class FileVersion(BaseModel):
    """A version created by squashing a collection of file deltas.

    A file delta represents one change to made to a file. By combining the base file version
    and the collection of delta changes, a specific version can be composed from history.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = Field(
        description="null if the latest unsaved version or not deleted"
    )
    created_by_id: Optional[UUID]

    number: Optional[int] = Field(
        description="v0, v1, ... unique per file, null if the latest unsaved version"
    )
    name: Optional[str] = Field(
        description="The name for this version, if not set the version is unnamed and "
        "the created_at datetime should be used to generate a name"
    )
    description: Optional[str]
    file_id: UUID
    project_id: UUID
    space_id: UUID

    # A presigned URL to retrieve the content of the version after all deltas were applied
    content_presigned_url: str
