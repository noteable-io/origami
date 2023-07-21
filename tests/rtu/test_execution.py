import asyncio

from origami.clients.api import APIClient
from origami.clients.rtu import RTUClient
from origami.models.api.files import File
from origami.models.kernels import KernelSession
from origami.models.notebook import CodeCell, Notebook


async def test_outputs(api_client: APIClient, notebook_maker):
    notebook = Notebook(cells=[CodeCell(id='cell_1', source='print("hello world"); 2 + 2')])
    file: File = await notebook_maker(notebook=notebook)
    # TODO: remove sleep when Gate stops permission denied on newly created files (db time-travel)
    await asyncio.sleep(2)

    rtu_client: RTUClient = await api_client.rtu_client(file.id)
    assert rtu_client.builder.nb.cells == notebook.cells

    kernel_session: KernelSession = await api_client.launch_kernel(file.id)
    await rtu_client.wait_for_kernel_idle()

    execute_event = await rtu_client.execute_cell('cell_1')
    # Assert cell_1 output collection has multiple outputs
    cell_1_output_collection_id = await execute_event  # wait for cell_1 to be done
    cell_1_output_collection = await api_client.get_output_collection(cell_1_output_collection_id)
    try:
        assert len(cell_1_output_collection.outputs) == 2
        assert cell_1_output_collection.outputs[0].content.raw == 'hello world\n'
        assert cell_1_output_collection.outputs[1].content.raw == '4'
    finally:
        await rtu_client.shutdown()
        await api_client.shutdown_kernel(kernel_session.id)
