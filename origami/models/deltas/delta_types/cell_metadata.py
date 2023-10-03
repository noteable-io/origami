from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from origami.models.deltas.base import FileDeltaBase

NULL_PRIOR_VALUE_SENTINEL = "__NULL_PRIOR_VALUE__"


class CellMetadataDelta(FileDeltaBase):
    delta_type: Literal["cell_metadata"] = "cell_metadata"


# A lot of state is stored in cell metadata, including DEX and execute time
class CellMetadataUpdateProperties(BaseModel):
    path: list
    value: Any
    prior_value: Any = NULL_PRIOR_VALUE_SENTINEL


class CellMetadataUpdate(CellMetadataDelta):
    # resource_id should be cell id to update
    delta_action: Literal["update"] = "update"
    properties: CellMetadataUpdateProperties


# Cell metadata replace is used for changing cell type and language (Python/R/etc)
class CellMetadataReplaceProperties(BaseModel):
    type: Optional[str]
    language: Optional[str]


class CellMetadataReplace(CellMetadataDelta):
    # resource_id should be cell id to replace
    delta_action: Literal["replace"] = "replace"
    properties: CellMetadataReplaceProperties


CellMetadataDeltas = Annotated[
    Union[
        CellMetadataUpdate,
        CellMetadataReplace,
    ],
    Field(discriminator="delta_action"),
]
