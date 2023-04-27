"""
The NotebookBuilder is used in applications that need to keep an in-memory representation of a
Notebook and update it with RTU / Delta formatted messages.
"""
import collections
import logging
import uuid
from typing import Callable, Dict, Optional, Tuple

import diff_match_patch
import nbformat
import orjson
import pydantic

from origami.defs import deltas
from origami.notebook.model import Notebook, NotebookCell

logger = logging.getLogger(__name__)


class CellNotFound(Exception):
    def __init__(self, cell_id: str):
        self.cell_id = cell_id

    def __str__(self):
        return f"Exception: Cell {self.cell_id} not found"


class NotebookBuilder:
    """
    Apply RTU File Deltas to an in-memory representation of a Notebook.

    # start with a seed Notebook
    from origami.notebook.model import Notebook
    nb = Notebook()

    # instantiate builder
    from origami.notebook.builder import NotebookBuilder
    builder = NotebookBuilder(seed_notebok=nb)

    # Apply deltas
    from orgami.defs import deltas
    deltas: List[deltas.FileDelta] = [...]
    for delta in deltas:
        builder.apply_delta(delta)

    # Get cell by ID, raises CellNotFound if id doesn't exist
    index, cell = builder.get_cell(cell_id='123')
    print(cell.source)

    # Serialize the notebook to JSON string (indent=False to make it more compact)
    output: str = builder.dumps(indent=True)
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

        self.last_applied_delta_id: Optional[uuid.UUID] = None
        # to keep track of deleted cells so we can ignore them in future deltas
        self.deleted_cell_ids: set[str] = set()

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

    def apply_delta(self, delta: deltas.FileDelta) -> None:
        """
        Entrypoint for applying deltas to the in-memory Notebook.
        Checks the delta type and delegates to the appropriate method.
        """
        # {delta_type: {delta_action: handler}}
        handlers: Dict[str, Dict[str, Callable]] = {
            "nb_cells": {
                "add": self.add_cell,
                "delete": self.delete_cell,
                "move": self.move_cell,
            },
            "cell_contents": {
                "update": self.update_cell_contents,
                "replace": self.replace_cell_contents,
            },
            "cell_metadata": {
                "update": self.update_cell_metadata,
                "replace": self.replace_cell_metadata,
            },
            "nb_metadata": {
                "update": self.update_notebook_metadata,
            },
            "cell_output_collection": {
                "replace": self.replace_cell_output_collection,
            },
            "cell_execute": {
                "execute": self.log_execute_delta,
                "execute_all": self.log_execute_delta,
                "execute_before": self.log_execute_delta,
                "execute_after": self.log_execute_delta,
            },
        }
        handler = None
        if delta.delta_type in handlers:
            handler = handlers[delta.delta_type].get(delta.delta_action)
        # We shouldn't expect to see out of order Deltas now that RTUClient is handling checking
        # order before trying to apply Deltas, but still log here if we think we're out of order
        if (
            delta.parent_delta_id
            and delta.parent_delta_id != deltas.NULL_PARENT_DELTA_SENTINEL
            and self.last_applied_delta_id
            and delta.parent_delta_id != self.last_applied_delta_id
        ):
            logger.warning(
                f"Suspect delta ordering: {delta.parent_delta_id=} {self.last_applied_delta_id=}"
            )
        # For observability sake, shout when we have a Delta type/action we aren't accounting for
        if not handler:
            logger.warning(
                f"Unhandled delta {delta.delta_type=} {delta.delta_action=}.\n\nFull Delta: {delta}"
            )
        else:
            handler(delta)
        # Even if the Delta was unhandled, update the last applied id so that we don't break
        # RTUClient by making it think we're waiting for a missing delta and blocking all applies
        self.last_applied_delta_id = delta.id

    def add_cell(self, delta: deltas.FileDelta):
        """Handles delta_type: nb_cells, delta_action: add"""
        props = deltas.NBCellProperties.parse_obj(delta.properties)
        if not props.cell:
            logger.warning("Received nb_cells / add delta with no cell data")
            return
        # Warning if we're adding a duplicate cell id
        if props.id in [cell.id for cell in self.nb.cells]:
            logger.warning(
                f"Received nb_cells / add delta with cell id {props.id}. There is already a cell with that id"  # noqa: E501
            )
        # Push 'id' down from NBCellProperties pydantic model into the actual props.cell dict
        # Should revisit this when reviewing RTU models
        props.cell["id"] = props.id
        # Convert props.cell from dict to NotebookCell
        new_cell = pydantic.parse_obj_as(NotebookCell, props.cell)
        if props.after_id:
            index, _ = self.get_cell(props.after_id)
            self.nb.cells.insert(index + 1, new_cell)
        else:
            self.nb.cells.insert(0, new_cell)

    def delete_cell(self, delta: deltas.FileDelta):
        """Handles delta_type: nb_cells, delta_action: delete"""
        props = deltas.NBCellProperties.parse_obj(delta.properties)
        if not props.id:
            logger.warning("Received nb_cells / delete delta with no cell id")
            return
        index, _ = self.get_cell(props.id)
        self.nb.cells.pop(index)
        self.deleted_cell_ids.add(props.id)

    def move_cell(self, delta: deltas.FileDelta):
        """Handles delta_type: nb_cells, delta_action: move"""
        props = deltas.NBCellProperties.parse_obj(delta.properties)
        # technically moving a cell "below itself" (id and after_id are the same) is a valid delta
        # but should effectively be a no-op from the NotebookBuilder perspective
        if props.id == props.after_id:
            return
        index, _ = self.get_cell(props.id)
        cell_to_move = self.nb.cells.pop(index)
        if props.after_id:
            target_index, _ = self.get_cell(props.after_id)
            self.nb.cells.insert(target_index + 1, cell_to_move)
        else:
            self.nb.cells.insert(0, cell_to_move)

    def update_cell_contents(self, delta: deltas.FileDelta):
        """Handles delta_type: cell_contents, delta_action: update"""
        props = deltas.V2CellContentsProperties.parse_obj(delta.properties)
        patches = self.dmp.patch_fromText(props.patch)

        _, cell = self.get_cell(delta.resource_id)
        merged_text = self.dmp.patch_apply(patches, cell.source)[0]
        cell.source = merged_text

    def replace_cell_contents(self, delta: deltas.FileDelta):
        """Handles delta_type: cell_contents, delta_action: replace"""
        props = deltas.V2CellContentsProperties.parse_obj(delta.properties)
        _, cell = self.get_cell(delta.resource_id)
        cell.source = props.source

    def update_notebook_metadata(self, delta: deltas.FileDelta):
        """Handles delta_type: nb_metadata, delta_action: update"""
        props = deltas.NBMetadataProperties.parse_obj(delta.properties)
        # Need to traverse the Notebook metadata dictionary by a list of keys.
        # If that key isn't there already, create it with value of empty dict
        # e.g. path=['foo', 'bar', 'baz'], value='xyz' needs to set
        # self.nb.metadata['foo']['bar']['baz'] = 'xyz'
        # and add those nested keys into metadata if they don't exist already
        dict_path = self.nb.metadata
        for leading_key in props.path[:-1]:
            if leading_key not in dict_path:
                dict_path[leading_key] = {}
            dict_path = dict_path[leading_key]

        last_key = props.path[-1]
        if (
            last_key in dict_path
            and props.prior_value
            and props.prior_value != deltas.NULL_PRIOR_VALUE_SENTINEL
            and dict_path[last_key] != props.prior_value
        ):
            logger.warning(
                f"Notebook metadata path {props.path} expected to have prior value {props.prior_value} but was {dict_path[last_key]}"  # noqa: E501
            )

        dict_path[last_key] = props.value

    def update_cell_metadata(self, delta: deltas.FileDelta):
        """Handles delta_type: cell_metadata, delta_action: update"""
        props = deltas.V2CellMetadataProperties.parse_obj(delta.properties)

        if delta.resource_id in self.deleted_cell_ids:
            logger.info(
                f"Skipping update_cell_metadata for deleted cell {delta.resource_id}",
                extra={'delta_properties_path': props.path},
            )
            return

        try:
            _, cell = self.get_cell(delta.resource_id)
        except CellNotFound:
            logger.warning(
                "Got update_cell_metadata for cell that isn't in notebook or deleted_cell_ids",  # noqa: E501
                extra={'delta_properties_path': props.path},
            )
            return

        # see comment in update_notebook_metadata explaining dictionary traversal
        dict_path = cell.metadata
        for leading_key in props.path[:-1]:
            if leading_key not in dict_path:
                dict_path[leading_key] = {}
            dict_path = dict_path[leading_key]

        last_key = props.path[-1]
        if (
            last_key in dict_path
            and props.prior_value
            and props.prior_value != deltas.NULL_PRIOR_VALUE_SENTINEL
            and str(dict_path[last_key]) != str(props.prior_value)
        ):
            logger.warning(
                f"Cell {cell.id} metadata path {props.path} expected to have prior value {props.prior_value} but was {dict_path[last_key]}"  # noqa: E501
            )

        dict_path[last_key] = props.value

    def replace_cell_metadata(self, delta: deltas.FileDelta):
        """
        Handles delta_type: cell_metadata, delta_action: replace.

        This typically happens when changing cell type (e.g. code -> markdown)
        """
        props = deltas.V2CellMetadataProperties.parse_obj(delta.properties)
        idx, cell = self.get_cell(delta.resource_id)

        if props.type:
            cell.cell_type = props.type
            # changing cell types, we need to re-model the cell and pop/insert it into our cell list
            cell = pydantic.parse_obj_as(NotebookCell, cell.dict())
            self.nb.cells.pop(idx)
            self.nb.cells.insert(idx, cell)
            if props.language:
                if "noteable" not in cell.metadata:
                    cell.metadata["noteable"] = {}
                cell.metadata["noteable"]["cell_type"] = props.language

    def replace_cell_output_collection(self, delta: deltas.FileDelta):
        """Handles delta_type: cell_output_collection, delta_action: replace"""
        if delta.resource_id in self.deleted_cell_ids:
            logger.info(
                f"Skipping replace_cell_output_collection for deleted cell {delta.resource_id}"
            )
            return

        props = deltas.V2CellOutputCollectionProperties.parse_obj(delta.properties)
        try:
            _, cell = self.get_cell(delta.resource_id)
        except CellNotFound:
            logger.warning(
                "Got replace_cell_output_collection for cell that isn't in notebook or deleted_cell_ids",  # noqa: E501
            )
            return

        if "noteable" not in cell.metadata:
            cell.metadata["noteable"] = {}
        cell.metadata["noteable"]["output_collection_id"] = props.output_collection_id

    def log_execute_delta(self, delta: deltas.FileDelta):
        """Handles delta_type: execute, delta_action: execute | execute_all"""
        pass

    def dumps(self, indent: bool = True) -> bytes:
        """
        Serialize the in-memory Notebook to JSON.
        """
        if indent:
            return orjson.dumps(self.nb.dict(exclude_unset=True), option=orjson.OPT_INDENT_2)
        else:
            return orjson.dumps(self.nb.dict(exclude_unset=True))
