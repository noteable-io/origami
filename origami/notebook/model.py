"""
Modeling the Notebook File Format with Pydantic models. It also includes some helper properties
relevant to Noteable format, such as whether a code cell is a SQL cell and retrieving the output
collection id, which is a Noteable-specific cell output context.

See https://nbformat.readthedocs.io/en/latest/format_description.html# for Notebook model spec.

Devs: as usual with Pydantic modeling, the top-level model (Notebook) is at the bottom of this file,
read from bottom up for most clarity.
"""
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator
from typing_extensions import Annotated  # for 3.8 compatibility


# Cell outputs modeled with a discriminator pattern where the output_type
# field will determine what kind of output we have
# https://nbformat.readthedocs.io/en/latest/format_description.html#code-cell-outputs
class StreamOutput(BaseModel):
    output_type: Literal["stream"] = "stream"
    name: str  # stdout or stderr
    text: str


class DisplayDataOutput(BaseModel):
    output_type: Literal["display_data"] = "display_data"
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class ExecuteResultOutput(BaseModel):
    output_type: Literal["execute_result"] = "execute_result"
    execution_count: Optional[int]
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class ErrorOutput(BaseModel):
    output_type: Literal["error"] = "error"
    ename: str
    evalue: str
    traceback: List[str]


# Use: List[CellOutput] or pydantic.parse_obj_as(CellOutput, dict)
CellOutput = Annotated[
    Union[StreamOutput, DisplayDataOutput, ExecuteResultOutput, ErrorOutput],
    Field(discriminator="output_type"),
]


# Cell types
class CellBase(BaseModel):
    """
    All Cell types have id, source and metadata.
    The source can be a string or list of strings in nbformat spec,
    but we only want to deal with source as a string throughout our
    code base so we have a validator here to cast the list of strings
    to a single string, both at initial read and during any mutations
    (e.g. applying diff-match-patch cell content updates).
    """

    id: str
    source: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("source", pre=True)
    def multiline_source(cls, v):
        if isinstance(v, list):
            return "\n".join(v)
        return v

    class Config:
        validate_on_assignment = True


class CodeCell(CellBase):
    cell_type: Literal["code"] = "code"
    execution_count: Optional[int]
    outputs: List[CellOutput] = Field(default_factory=list)

    @property
    def is_sql_cell(self):
        return self.metadata.get("noteable", {}).get("cell_type") == "sql"

    @property
    def output_collection_id(self) -> Optional[Union[str, uuid.UUID]]:
        return self.metadata.get("noteable", {}).get("output_collection_id")


class MarkdownCell(CellBase):
    cell_type: Literal["markdown"] = "markdown"


class RawCell(CellBase):
    cell_type: Literal["raw"] = "raw"


# Use: List[NotebookCell] or pydantic.parse_obj_as(NotebookCell, dict)
NotebookCell = Annotated[
    Union[
        CodeCell,
        MarkdownCell,
        RawCell,
    ],
    Field(discriminator="cell_type"),
]


class Notebook(BaseModel):
    nbformat: int
    nbformat_minor: int
    metadata: Dict[str, Any]
    cells: List[NotebookCell]

    @property
    def language(self) -> Optional[str]:
        return self.metadata.get("language_info", {}).get("name")

    @property
    def language_version(self) -> Optional[str]:
        return self.metadata.get("language_info", {}).get("version")
