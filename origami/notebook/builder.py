"""
The NotebookBuilder is used in applications that need to keep an in-memory representation of a
Notebook and update it with RTU / Delta formatted messages.
"""
import collections
import logging
import uuid
from typing import Callable, Dict, Optional, Tuple, Type, Union

import diff_match_patch
import nbformat
import orjson

from origami.models.deltas.delta_types.cell_contents import CellContentsReplace, CellContentsUpdate
from origami.models.deltas.delta_types.cell_execute import (
    CellExecute,
    CellExecuteAfter,
    CellExecuteAll,
    CellExecuteBefore,
)
from origami.models.deltas.delta_types.cell_metadata import (
    NULL_PRIOR_VALUE_SENTINEL,
    CellMetadataReplace,
    CellMetadataUpdate,
)
from origami.models.deltas.delta_types.cell_output_collection import CellOutputCollectionReplace
from origami.models.deltas.delta_types.nb_cells import NBCellsAdd, NBCellsDelete, NBCellsMove
from origami.models.deltas.delta_types.nb_metadata import NBMetadataUpdate
from origami.models.deltas.discriminators import FileDelta
from origami.models.notebook import Notebook, NotebookCell

logger = logging.getLogger(__name__)


class CellNotFound(Exception):
    def __init__(self, cell_id: str):
        self.cell_id = cell_id

    def __str__(self):
        return f"Exception: Cell {self.cell_id} not found"


class NotebookBuilder:
    """
    Apply RTU File Deltas to an in-memory representation of a Notebook.
    """

    def __init__(self, seed_notebook: Notebook):
        if not isinstance(seed_notebook, Notebook):
            raise TypeError("seed_notebook must be a Pydantic Notebook model")
        self._seed_notebook = seed_notebook
        self.nb: Notebook = seed_notebook.copy()
        self.dmp = diff_match_patch.diff_match_patch()

        cell_id_counts = collections.defaultdict(int)
        for cell in self.nb.cells:
            cell_id_counts[cell.id] += 1
        for cell_id, count in cell_id_counts.items():
            if count > 1:
                logger.warning(f"Found {count} cells with id {cell_id}")

        # RTUClient uses the builder.last_applied_delta_id to figure out whether to apply incoming
        # deltas or queue them in an unapplied_deltas list for replay
        self.last_applied_delta_id: Optional[uuid.UUID] = None
        # to keep track of deleted cells so we can ignore them in future deltas
        self.deleted_cell_ids: set[str] = set()

    @property
    def cell_ids(self) -> list[str]:
        return [cell.id for cell in self.nb.cells]

    @classmethod
    def from_nbformat(self, nb: nbformat.NotebookNode) -> "NotebookBuilder":
        """Instantiate a NotebookBuilder from a nbformat NotebookNode"""
        nb = Notebook.parse_obj(nb.dict())
        return NotebookBuilder(nb)

    def get_cell(self, cell_id: str) -> Tuple[int, NotebookCell]:
        """
        Convenience method to return a cell by cell id.
        Raises CellNotFound if cell id is not in the Notebook
        """
        for index, cell in enumerate(self.nb.cells):
            if cell.id == cell_id:
                return (index, cell)
        raise CellNotFound(cell_id)

    def apply_delta(self, delta: FileDelta) -> None:
        """
        Apply a FileDelta to the NotebookBuilder.
        """
        handlers: Dict[Type[FileDelta], Callable] = {
            NBCellsAdd: self.add_cell,
            NBCellsDelete: self.delete_cell,
            NBCellsMove: self.move_cell,
            CellContentsUpdate: self.update_cell_contents,
            CellContentsReplace: self.replace_cell_contents,
            CellMetadataUpdate: self.update_cell_metadata,
            CellMetadataReplace: self.replace_cell_metadata,
            NBMetadataUpdate: self.update_notebook_metadata,
            CellOutputCollectionReplace: self.replace_cell_output_collection,
            CellExecute: self.log_execute_delta,
            CellExecuteAll: self.log_execute_delta,
            CellExecuteBefore: self.log_execute_delta,
            CellExecuteAfter: self.log_execute_delta,
        }
        if type(delta) not in handlers:
            raise ValueError(f"No handler for {delta.delta_type=}, {delta.delta_action=}")

        handler = handlers[type(delta)]
        try:
            handler(delta)
            self.last_applied_delta_id = delta.id
        except Exception as e:  # noqa: E722
            logger.exception("Error squashing Delta into NotebookBuilder", extra={'delta': delta})
            raise e

    def add_cell(self, delta: NBCellsAdd):
        """
        Add a new cell to the Notebook.
         - If after_id is specified, add it after that cell. Otherwise at top of Notebook
         - cell_id can be specified at higher level delta.properties and should be copied down into
           the cell part of the delta.properties
        """
        cell_id = delta.properties.id
        # Warning if we're adding a duplicate cell id
        if cell_id in self.cell_ids:
            logger.warning(
                f"Received NBCellsAdd delta with cell id {cell_id}, duplicate of existing cell"
            )
        new_cell = delta.properties.cell
        # Push "delta.properites.id" down into cell id ...
        new_cell.id = cell_id
        if delta.properties.after_id:
            index, _ = self.get_cell(delta.properties.after_id)
            self.nb.cells.insert(index + 1, new_cell)
        else:
            self.nb.cells.insert(0, new_cell)

    def delete_cell(self, delta: NBCellsDelete):
        """Deletes a cell from the Notebook. If the cell can't be found, warn but don't error."""
        cell_id = delta.properties.id
        index, _ = self.get_cell(cell_id)
        self.nb.cells.pop(index)
        self.deleted_cell_ids.add(cell_id)

    def move_cell(self, delta: NBCellsMove):
        """Moves a cell from one position to another in the Notebook"""
        cell_id = delta.properties.id
        index, _ = self.get_cell(cell_id)
        cell_to_move = self.nb.cells.pop(index)
        if delta.properties.after_id:
            target_index, _ = self.get_cell(delta.properties.after_id)
            self.nb.cells.insert(target_index + 1, cell_to_move)
            return
        else:
            self.nb.cells.insert(0, cell_to_move)

    def update_cell_contents(self, delta: CellContentsUpdate):
        """Update cell content using the diff-match-patch algorithm"""
        patches = self.dmp.patch_fromText(delta.properties.patch)
        _, cell = self.get_cell(delta.resource_id)
        merged_text = self.dmp.patch_apply(patches, cell.source)[0]
        cell.source = merged_text

    def replace_cell_contents(self, delta: CellContentsReplace):
        """Pure replacement of cell source content"""
        _, cell = self.get_cell(delta.resource_id)
        cell.source = delta.properties.source

    def update_notebook_metadata(self, delta: NBMetadataUpdate):
        """Update top-level Notebook metadata using a partial update / nested path technique"""
        # Need to traverse the Notebook metadata dictionary by a list of keys.
        # If that key isn't there already, create it with value of empty dict
        # e.g. path=['foo', 'bar', 'baz'], value='xyz' needs to set
        # self.nb.metadata['foo']['bar']['baz'] = 'xyz'
        # and add those nested keys into metadata if they don't exist already
        dict_path = self.nb.metadata
        for leading_key in delta.properties.path[:-1]:
            if leading_key not in dict_path:
                dict_path[leading_key] = {}
            dict_path = dict_path[leading_key]

        last_key = delta.properties.path[-1]
        if (
            last_key in dict_path
            and delta.properties.prior_value
            and delta.properties.prior_value != NULL_PRIOR_VALUE_SENTINEL
            and dict_path[last_key] != delta.properties.prior_value
        ):
            logger.warning(
                f"Notebook metadata path {delta.properties.path} expected to have prior value {delta.properties.prior_value} but was {dict_path[last_key]}"  # noqa: E501
            )

        dict_path[last_key] = delta.properties.value

    def update_cell_metadata(self, delta: CellMetadataUpdate):
        """Update cell metadata using a partial update / nested path technique"""
        if delta.resource_id in self.deleted_cell_ids:
            logger.info(
                f"Skipping update_cell_metadata for deleted cell {delta.resource_id}",
                extra={'delta_properties_path': delta.properties.path},
            )
            return

        try:
            _, cell = self.get_cell(delta.resource_id)
        except CellNotFound:
            # Most often happens when a User deletes a cell that's in progress of being executed,
            # and we end up emitting a cell execution timing metadata as it gets deleted
            logger.warning(
                "Got update_cell_metadata for cell that isn't in notebook or deleted_cell_ids",  # noqa: E501
                extra={'delta_properties_path': delta.properties.path},
            )
            return

        # see comment in update_notebook_metadata explaining dictionary traversal
        dict_path = cell.metadata
        for leading_key in delta.properties.path[:-1]:
            if leading_key not in dict_path:
                dict_path[leading_key] = {}
            dict_path = dict_path[leading_key]

        last_key = delta.properties.path[-1]
        if (
            last_key in dict_path
            and delta.properties.prior_value
            and delta.properties.prior_value != NULL_PRIOR_VALUE_SENTINEL
            and str(dict_path[last_key]) != str(delta.properties.prior_value)
        ):
            logger.warning(
                f"Cell {cell.id} metadata path {delta.properties.path} expected to have prior value {delta.properties.prior_value} but was {dict_path[last_key]}"  # noqa: E501
            )

        dict_path[last_key] = delta.properties.value

    def replace_cell_metadata(self, delta: CellMetadataReplace):
        """Switch a cell type between code / markdown or change cell language (e.g. Python to R)"""
        _, cell = self.get_cell(delta.resource_id)

        if delta.properties.type:
            cell.cell_type = delta.properties.type
        if delta.properties.language:
            if "noteable" not in cell.metadata:
                cell.metadata["noteable"] = {}
            cell.metadata["noteable"]["cell_type"] = delta.properties.language

    def replace_cell_output_collection(self, delta: CellOutputCollectionReplace):
        """Update cell metadata to point to an Output Collection container id"""
        if delta.resource_id in self.deleted_cell_ids:
            logger.warning(
                f"Skipping replace_cell_output_collection for deleted cell {delta.resource_id}"
            )
            return

        try:
            _, cell = self.get_cell(delta.resource_id)
        except CellNotFound:
            logger.warning(
                "Got replace_cell_output_collection for cell that isn't in notebook or deleted_cell_ids",  # noqa: E501
            )
            return

        if "noteable" not in cell.metadata:
            cell.metadata["noteable"] = {}
        cell.metadata["noteable"]["output_collection_id"] = delta.properties.output_collection_id

    def log_execute_delta(
        self, delta: Union[CellExecute, CellExecuteBefore, CellExecuteAfter, CellExecuteAll]
    ):
        """Handles delta_type: execute, delta_action: execute | execute_all"""
        logger.debug(
            "Squashing execute delta",
            extra={"delta_type": delta.delta_type, "delta_action": delta.delta_action},
        )
        pass

    def dumps(self, indent: bool = True) -> bytes:
        """
        Serialize the in-memory Notebook to JSON.
        """
        if indent:
            return orjson.dumps(self.nb.dict(exclude_unset=True), option=orjson.OPT_INDENT_2)
        else:
            return orjson.dumps(self.nb.dict(exclude_unset=True))
