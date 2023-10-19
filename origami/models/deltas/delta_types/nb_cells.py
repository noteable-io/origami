from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from origami.models.deltas.base import FileDeltaBase
from origami.models.notebook import NotebookCell


class NBCellsDelta(FileDeltaBase):
    delta_type: Literal["nb_cells"] = "nb_cells"


class NBCellsAddProperties(BaseModel):
    id: str  # should be same as cell.id
    after_id: Optional[str] = None  # insert this cell after another cell in the Notebook
    cell: NotebookCell


class NBCellsAdd(NBCellsDelta):
    delta_action: Literal["add"] = "add"
    properties: NBCellsAddProperties


class NBCellsDeleteProperties(BaseModel):
    id: str


class NBCellsDelete(NBCellsDelta):
    delta_action: Literal["delete"] = "delete"
    properties: NBCellsDeleteProperties


class NBCellsMoveProperties(BaseModel):
    id: str
    after_id: Optional[str] = None


class NBCellsMove(NBCellsDelta):
    delta_action: Literal["move"] = "move"
    properties: NBCellsMoveProperties


NBCellsDeltas = Annotated[
    Union[
        NBCellsAdd,
        NBCellsDelete,
        NBCellsMove,
    ],
    Field(discriminator="delta_action"),
]
