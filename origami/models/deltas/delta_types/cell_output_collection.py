import uuid
from typing import Literal

from pydantic import BaseModel

from origami.models.deltas.base import FileDeltaBase


class CellOutputCollectionDelta(FileDeltaBase):
    delta_type: Literal["cell_output_collection"] = "cell_output_collection"


class CellOutputCollectionReplaceData(BaseModel):
    output_collection_id: uuid.UUID


class CellOutputCollectionReplace(CellOutputCollectionDelta):
    # resource_id should be cell id to replace with new output ocllection id
    delta_action: Literal["replace"] = "replace"
    properties: CellOutputCollectionReplaceData


# Since there's only one action, we don't have an Annotated Union
CellOutputCollectionDeltas = CellOutputCollectionReplace
