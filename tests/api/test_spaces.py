import uuid

from origami.clients.api import APIClient
from origami.models.api_resources import Project, Space


async def test_space_crud(api_client: APIClient):
    name = 'test-space-' + str(uuid.uuid4())
    space = await api_client.create_space(name=name)
    assert isinstance(space, Space)
    assert space.name == name

    existing_space = await api_client.get_space(space.id)
    assert existing_space.id == space.id
    assert existing_space.name == name

    deleted_space = await api_client.delete_space(space.id)
    assert deleted_space.id == space.id
    assert deleted_space.deleted_at is not None


async def test_list_space_projects(
    api_client: APIClient,
    test_space_id: uuid.UUID,
    new_project: Project,
):
    projects = await api_client.list_space_projects(test_space_id)
    assert len(projects) > 0
    assert isinstance(projects[0], Project)
    assert new_project.id in [p.id for p in projects]
