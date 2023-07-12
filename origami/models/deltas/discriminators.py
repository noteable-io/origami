from typing import Annotated, Union

from pydantic import Field

from origami.models.deltas.delta_types.cell_contents import CellContentsDeltas
from origami.models.deltas.delta_types.cell_execute import CellExecuteDeltas
from origami.models.deltas.delta_types.cell_metadata import CellMetadataDeltas
from origami.models.deltas.delta_types.cell_output_collection import CellOutputCollectionDeltas
from origami.models.deltas.delta_types.nb_cells import NBCellsDeltas
from origami.models.deltas.delta_types.nb_metadata import NBMetadataDeltas

# Use: pydantic.pares_obj_as(FileDelta, <payload-as-dict>)
FileDelta = Annotated[
    Union[
        CellContentsDeltas,
        CellExecuteDeltas,
        CellMetadataDeltas,
        CellOutputCollectionDeltas,
        NBCellsDeltas,
        NBMetadataDeltas,
    ],
    Field(discriminator="delta_type"),
]
