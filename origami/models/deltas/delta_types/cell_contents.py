from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from origami.models.deltas.base import FileDeltaBase


class CellContentsDelta(FileDeltaBase):
    delta_type: Literal["cell_contents"] = "cell_contents"


class CellContentsUpdateProperties(BaseModel):
    patch: str  # diff-match-patch


class CellContentsUpdate(CellContentsDelta):
    # resource_id should be cell id to update
    delta_action: Literal["update"] = "update"
    properties: CellContentsUpdateProperties


class CellContentsReplaceProperties(BaseModel):
    source: str  # full replace, no diff-match-patch


class CellContentsReplace(CellContentsDelta):
    # resource_id should be cell id to replace
    delta_action: Literal["replace"] = "replace"
    properties: CellContentsReplaceProperties


CellContentsDeltas = Annotated[
    Union[
        CellContentsUpdate,
        CellContentsReplace,
    ],
    Field(discriminator="delta_action"),
]
