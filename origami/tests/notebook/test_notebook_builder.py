import uuid

import nbformat
import pytest

from origami.defs import deltas
from origami.notebook.builder import CellNotFound, NotebookBuilder
from origami.notebook.model import CodeCell, MarkdownCell


def test_notebook_builder():
    """
    Test that applying some deltas to a notebook works as expected.
      - Add a cell
      - Modify content using diff-match-patch
      - Insert a new cell
      - Drag cell up to top of Notebook
      - Try to do something with a cell id that doesn't exist
    """
    file_id = uuid.uuid4()  # doesn't matter for this test, required for Deltas though
    seed_notebook = nbformat.v4.new_notebook()
    assert str(seed_notebook) == "{'nbformat': 4, 'nbformat_minor': 5, 'metadata': {}, 'cells': []}"

    builder = NotebookBuilder.from_nbformat(seed_notebook)
    assert (
        builder.dumps(indent=False) == b'{"nbformat":4,"nbformat_minor":5,"metadata":{},"cells":[]}'
    )

    # Add a new cell
    first_cell_data = deltas.NBCellDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="nb_cells",
        delta_action="add",
        resource_id=deltas.NULL_RESOURCE_SENTINEL,
        properties=deltas.NBCellProperties(
            id="cell1",
            cell={
                "cell_type": "code",
                "execution_count": None,
                "metadata": {
                    "jupyter": {"source_hidden": False, "outputs_hidden": False},
                    "noteable": {"cell_type": "code"},
                },
                "source": "x = 1",
                "outputs": [],
            },
        ),
    )
    builder.apply_delta(delta=first_cell_data)

    assert builder.nb.cells[0].id == "cell1"
    assert builder.nb.cells[0].source == "x = 1"

    # user types a second line in the cell, y = 2
    cell_update_1 = deltas.CellContentsDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_contents",
        delta_action="update",
        resource_id="cell1",
        properties=deltas.V2CellContentsProperties(patch="@@ -1,5 +1,11 @@\n x = 1\n+%0Ay = 2\n"),
    )

    # user updates the first line from x = 1 to x = 5
    cell_update_2 = deltas.CellContentsDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_contents",
        delta_action="update",
        resource_id="cell1",
        properties=deltas.V2CellContentsProperties(
            patch="@@ -1,9 +1,9 @@\n x = \n-1\n+5\n %0Ay =\n"
        ),
    )

    builder.apply_delta(delta=cell_update_1)
    builder.apply_delta(delta=cell_update_2)
    assert builder.nb.cells[0].source == "x = 5\ny = 2"

    # Insert new cell in front of cell1
    second_cell_data = deltas.NBCellDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="nb_cells",
        delta_action="add",
        resource_id=deltas.NULL_RESOURCE_SENTINEL,
        properties=deltas.NBCellProperties(
            id="cell2",
            after_id=None,
            cell={
                "cell_type": "code",
                "execution_count": None,
                "metadata": {
                    "jupyter": {"source_hidden": False, "outputs_hidden": False},
                    "noteable": {"cell_type": "code"},
                },
                "source": "z = 7",
            },
        ),
    )
    builder.apply_delta(delta=second_cell_data)

    assert builder.nb.cells[0].id == "cell2"
    assert builder.nb.cells[1].id == "cell1"

    # Move cell1 back to top of Notebook
    cell_move_data = deltas.NBCellDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="nb_cells",
        delta_action="move",
        resource_id=deltas.NULL_RESOURCE_SENTINEL,
        properties=deltas.NBCellProperties(id="cell1", after_id=None),
    )
    builder.apply_delta(delta=cell_move_data)

    assert builder.nb.cells[0].id == "cell1"
    assert builder.nb.cells[1].id == "cell2"

    # Try to apply a delta to a cell that doesn't exist
    non_existent_cell_move = deltas.NBCellDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="nb_cells",
        delta_action="move",
        resource_id=deltas.NULL_RESOURCE_SENTINEL,
        properties=deltas.NBCellProperties(id="cell420", after_id=None),
    )

    with pytest.raises(CellNotFound):
        builder.apply_delta(delta=non_existent_cell_move)

    # Switch cell1 to markdown
    cell1_to_markdown = deltas.CellMetadataDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_metadata",
        delta_action="replace",
        resource_id="cell1",
        properties=deltas.V2CellMetadataProperties(language="markdown", type="markdown"),
    )
    builder.apply_delta(delta=cell1_to_markdown)

    assert builder.nb.cells[0].cell_type == "markdown"

    # Switch cell1 back to code
    cell1_to_code = deltas.CellMetadataDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_metadata",
        delta_action="replace",
        resource_id="cell1",
        properties=deltas.V2CellMetadataProperties(language="python", type="code"),
    )
    builder.apply_delta(delta=cell1_to_code)

    assert builder.nb.cells[0].cell_type == "code"

    # Replace cell1 code content
    cell1_code_replace = deltas.CellContentsDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_contents",
        delta_action="replace",
        resource_id="cell1",
        properties=deltas.V2CellContentsProperties(source="x = 5"),
    )
    builder.apply_delta(delta=cell1_code_replace)

    assert builder.nb.cells[0].source == "x = 5"


def test_cell_type_switch():
    """
    Test that when a user switches a cell from code to markdown and back, the cell model
    is updated in our in-memory Notebook/Builder. This is important because some parts
    of the execution flow use properties only set on CodeCell models.
    """
    file_id = uuid.uuid4()  # doesn't matter for this test, required for Deltas though
    seed_notebook = nbformat.v4.new_notebook()
    seed_notebook.cells.append(nbformat.v4.new_code_cell(id="cell1", source="x = 1"))
    seed_notebook.cells.append(nbformat.v4.new_code_cell(id="cell2", source="y = 2"))
    seed_notebook.cells.append(nbformat.v4.new_code_cell(id="cell3", source="z = 3"))
    builder = NotebookBuilder.from_nbformat(seed_notebook)
    idx, cell2 = builder.get_cell("cell2")
    assert idx == 1
    assert isinstance(cell2, CodeCell)

    # Switch cell1 to markdown
    to_markdown_delta = deltas.CellMetadataDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_metadata",
        delta_action="replace",
        resource_id="cell2",
        properties=deltas.V2CellMetadataProperties(type="markdown"),
    )
    builder.apply_delta(delta=to_markdown_delta)

    idx, cell2 = builder.get_cell("cell2")
    assert idx == 1
    assert isinstance(cell2, MarkdownCell)

    # Switch back to code
    to_code_delta = deltas.CellMetadataDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="cell_metadata",
        delta_action="replace",
        resource_id="cell2",
        properties=deltas.V2CellMetadataProperties(type="code"),
    )
    builder.apply_delta(delta=to_code_delta)

    idx, cell2 = builder.get_cell("cell2")
    assert idx == 1
    assert isinstance(cell2, CodeCell)


def test_move_cell_below_itself():
    """
    Test for ENG-5462. It's technically possible to generate a cell move delta where the
    id and after_id are the same (moving a cell "below itself"), and that broke PA at
    one point in time.
    """
    file_id = uuid.uuid4()  # doesn't matter for this test, required for Deltas though
    seed_notebook = nbformat.v4.new_notebook()
    seed_notebook.cells.append(nbformat.v4.new_code_cell(id="cell1", source="x = 1"))
    seed_notebook.cells.append(nbformat.v4.new_code_cell(id="cell2", source="y = 2"))
    builder = NotebookBuilder.from_nbformat(seed_notebook)

    # Move cell1 below itself, assert Notebook is still how we expect
    move_delta = deltas.NBCellDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="nb_cells",
        delta_action="move",
        resource_id=deltas.NULL_RESOURCE_SENTINEL,
        properties=deltas.NBCellProperties(id="cell1", after_id="cell1"),
    )
    builder.apply_delta(delta=move_delta)

    assert builder.nb.cells[0].id == "cell1"
    assert builder.nb.cells[1].id == "cell2"

    # Move cell1 below cell2, assert Notebook is still how we expect
    move_delta = deltas.NBCellDelta(
        id=uuid.uuid4(),
        file_id=file_id,
        delta_type="nb_cells",
        delta_action="move",
        resource_id=deltas.NULL_RESOURCE_SENTINEL,
        properties=deltas.NBCellProperties(id="cell1", after_id="cell2"),
    )
    builder.apply_delta(delta=move_delta)

    assert builder.nb.cells[0].id == "cell2"
    assert builder.nb.cells[1].id == "cell1"


def test_clear_output():
    """
    Test created after hotfix to release/england. If a cell metadata update came in with a path
    and a prior value that was not null, we would check the cell metadata path to compare value to
    prior value. But if we didn't have any metadata in that cell, we would key error on the path.

    This test proves the squashing behavior is fixed.
    """
    seed_notebook = nbformat.v4.new_notebook()
    seed_notebook.cells.append(nbformat.v4.new_code_cell(id="cell1", source="x = 1"))
    nb_builder = NotebookBuilder.from_nbformat(nbformat.v4.new_notebook())

    delta = deltas.CellMetadataDelta(
        id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        delta_type="cell_metadata",
        delta_action="update",
        resource_id="cell1",
        properties={
            "path": ["noteable", "output_collection_id"],
            "value": None,
            "prior_value": str(uuid.uuid4()),
        },
    )
    nb_builder.apply_delta(delta)
