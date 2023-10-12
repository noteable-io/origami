import asyncio

import pytest

from origami.clients.api import APIClient
from origami.clients.rtu import RTUClient
from origami.models.api.files import File
from origami.notebook.builder import CellNotFound


async def test_add_and_remove_cell(api_client: APIClient, notebook_maker):
    file: File = await notebook_maker()
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)
    rtu_client: RTUClient = await api_client.connect_realtime(file)
    try:
        assert rtu_client.builder.nb.cells == []

        cell = await rtu_client.add_cell(source='print("hello world")')
        assert cell.cell_type == "code"
        assert cell.id in rtu_client.cell_ids

        await rtu_client.delete_cell(cell.id)
        with pytest.raises(CellNotFound):
            rtu_client.builder.get_cell(cell.id)
    finally:
        await rtu_client.shutdown()


async def test_change_cell_type(api_client: APIClient, notebook_maker):
    file: File = await notebook_maker()
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)
    rtu_client: RTUClient = await api_client.connect_realtime(file)
    try:
        assert rtu_client.builder.nb.cells == []

        source_cell = await rtu_client.add_cell(source="1 + 1")
        _, cell = rtu_client.builder.get_cell(source_cell.id)
        assert cell.cell_type == "code"

        await rtu_client.change_cell_type(cell.id, "markdown")
        _, cell = rtu_client.builder.get_cell(source_cell.id)
        assert cell.cell_type == "markdown"

        await rtu_client.change_cell_type(cell.id, "sql")
        _, cell = rtu_client.builder.get_cell(source_cell.id)
        assert cell.cell_type == "code"
        assert cell.is_sql_cell
    finally:
        await rtu_client.shutdown()


async def test_update_cell_content(api_client: APIClient, notebook_maker):
    file: File = await notebook_maker()
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)
    rtu_client: RTUClient = await api_client.connect_realtime(file)
    try:
        assert rtu_client.builder.nb.cells == []

        source_cell = await rtu_client.add_cell(source="1 + 1")
        _, cell = rtu_client.builder.get_cell(source_cell.id)

        cell = await rtu_client.update_cell_content(cell.id, "@@ -1,5 +1,5 @@\n-1 + 1\n+2 + 2\n")
        assert cell.source == "2 + 2"
    finally:
        await rtu_client.shutdown()


async def test_replace_cell_content(api_client: APIClient, notebook_maker):
    file: File = await notebook_maker()
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)
    rtu_client: RTUClient = await api_client.connect_realtime(file)
    try:
        assert rtu_client.builder.nb.cells == []

        source_cell = await rtu_client.add_cell(source="1 + 1")
        _, cell = rtu_client.builder.get_cell(source_cell.id)

        cell = await rtu_client.replace_cell_content(cell.id, "2 + 2")
        assert cell.source == "2 + 2"
    finally:
        await rtu_client.shutdown()
