import uuid

from origami.clients.api import APIClient
from origami.models.api.files import File
from origami.models.api.projects import Project


async def test_project_crud(api_client: APIClient, test_space_id: uuid.UUID):
    name = 'test-project-' + str(uuid.uuid4())
    project = await api_client.create_project(name=name, space_id=test_space_id)
    assert isinstance(project, Project)
    assert project.name == name

    existing_project = await api_client.get_project(project.id)
    assert existing_project.id == project.id
    assert existing_project.name == name

    deleted_project = await api_client.delete_project(project.id)
    assert deleted_project.id == project.id
    assert deleted_project.deleted_at is not None


async def test_list_project_files(
    api_client: APIClient, test_project_id: uuid.UUID, file_maker, notebook_maker
):
    salt = str(uuid.uuid4())
    flat_file: File = await file_maker(test_project_id, f'flat-file-{salt}.txt', b'flat file')
    notebook: File = await notebook_maker(test_project_id, f'nested/notebook-{salt}.ipynb')
    file_list = await api_client.list_project_files(test_project_id)
    assert len(file_list) > 0
    assert isinstance(file_list[0], File)
    file_ids = [f.id for f in file_list]
    assert flat_file.id in file_ids
    assert notebook.id in file_ids
