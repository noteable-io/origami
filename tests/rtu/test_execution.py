import asyncio

from origami.clients.api import APIClient
from origami.clients.rtu import RTUClient
from origami.models.api.files import File
from origami.models.api.outputs import KernelOutputCollection
from origami.models.kernels import KernelSession
from origami.models.notebook import CodeCell, MarkdownCell, Notebook


async def test_single_cell(api_client: APIClient, notebook_maker):
    notebook = Notebook(cells=[CodeCell(id='cell_1', source='print("hello world"); 2 + 2')])
    file: File = await notebook_maker(notebook=notebook)
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)

    rtu_client: RTUClient = await api_client.rtu_client(file.id)
    assert rtu_client.builder.nb.cells == notebook.cells

    kernel_session: KernelSession = await api_client.launch_kernel(file.id)
    await rtu_client.wait_for_kernel_idle()

    queued_execution = await rtu_client.queue_execute('cell_1')
    # Assert cell_1 output collection has multiple outputs
    cell: CodeCell = await queued_execution  # wait for cell_1 to be done
    output_collection: KernelOutputCollection = await api_client.get_output_collection(
        cell.output_collection_id
    )
    try:
        assert len(output_collection.outputs) == 2
        assert output_collection.outputs[0].content.raw == 'hello world\n'
        assert output_collection.outputs[1].content.raw == '4'
    finally:
        await rtu_client.shutdown()
        await api_client.shutdown_kernel(kernel_session.id)


async def test_run_all(api_client: APIClient, notebook_maker):
    notebook = Notebook(
        cells=[
            CodeCell(id='cell_1', source='2 + 2'),
            MarkdownCell(source="## a header"),
            CodeCell(id='cell_2', source='3 + 3'),
        ]
    )
    file: File = await notebook_maker(notebook=notebook)
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)

    rtu_client: RTUClient = await api_client.rtu_client(file.id)
    assert rtu_client.builder.nb.cells == notebook.cells

    kernel_session: KernelSession = await api_client.launch_kernel(file.id)
    await rtu_client.wait_for_kernel_idle()

    queued_execution = await rtu_client.queue_execute(run_all=True)
    # should only get two futures back, one for each code cell
    assert len(queued_execution) == 2
    cells = await asyncio.gather(*queued_execution)
    cell1_output = await api_client.get_output_collection(cells[0].output_collection_id)
    cell2_output = await api_client.get_output_collection(cells[1].output_collection_id)
    try:
        assert cell1_output.outputs[0].content.raw == '4'
        assert cell2_output.outputs[0].content.raw == '6'
    finally:
        await rtu_client.shutdown()
        await api_client.shutdown_kernel(kernel_session.id)
