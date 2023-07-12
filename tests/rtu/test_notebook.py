import asyncio

import pytest

from origami.clients.api import APIClient
from origami.clients.rtu import RTUClient
from origami.models.api_resources import File
from origami.models.notebook import CodeCell
from origami.notebook.builder import CellNotFound


async def test_add_and_remove_cell(api_client: APIClient, notebook_maker):
    file: File = await notebook_maker()
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)
    rtu_client: RTUClient = await api_client.rtu_client(file.id)
    assert rtu_client.builder.nb.cells == []

    cell = CodeCell(id='cell_1', source='print("hello world")')
    await rtu_client.add_cell(cell)
    _, squashed_cell = rtu_client.builder.get_cell(cell.id)
    assert squashed_cell.source == cell.source

    await rtu_client.delete_cell(cell.id)
    with pytest.raises(CellNotFound):
        rtu_client.builder.get_cell(cell.id)

    await rtu_client.shutdown()
