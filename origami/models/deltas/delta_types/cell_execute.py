from typing import Annotated, Literal, Union

from pydantic import Field

from origami.models.deltas.base import FileDeltaBase


class CellExecuteDelta(FileDeltaBase):
    delta_type: Literal["cell_execute"] = "cell_execute"


class CellExecute(CellExecuteDelta):
    # execute single cel
    # resource_id should be cell id to run
    delta_action: Literal['execute'] = 'execute'


class CellExecuteAfter(CellExecuteDelta):
    # execute specific cell id and all cells after it
    # resource_id should be cell id to run
    delta_action: Literal['execute_after'] = 'execute_after'


class CellExecuteBefore(CellExecuteDelta):
    # execute all cells up to specific cell, inclusive of that cell id
    # resource_id should be cell id to run
    delta_action: Literal['execute_before'] = 'execute_before'


class CellExecuteAll(CellExecuteDelta):
    # execute all cells
    delta_action: Literal['execute_all'] = 'execute_all'


CellExecuteDeltas = Annotated[
    Union[
        CellExecute,
        CellExecuteAfter,
        CellExecuteBefore,
        CellExecuteAll,
    ],
    Field(discriminator="delta_action"),
]
