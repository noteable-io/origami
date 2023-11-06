from typing import Any, Literal, Optional

from pydantic import BaseModel

from origami.models.deltas.base import FileDeltaBase


class NBMetadataDelta(FileDeltaBase):
    delta_type: Literal["nb_metadata"] = "nb_metadata"


class NBMetadataProperties(BaseModel):
    path: list
    value: Any = None
    prior_value: Optional[Any] = None


class NBMetadataUpdate(NBMetadataDelta):
    delta_action: Literal["update"] = "update"
    properties: NBMetadataProperties


# Since there's only one option here, instead of annotated union we alias this to the single item
NBMetadataDeltas = NBMetadataUpdate
