import uuid

import httpx

from origami.clients.api import APIClient
from origami.models.api.files import File


async def test_file_crud(api_client: APIClient, test_project_id):
    name = uuid.uuid4().hex + ".txt"
    content = b"foo\nbar\nbaz"
    new_file = await api_client.create_file(project_id=test_project_id, path=name, content=content)
    assert new_file.filename == name
    assert new_file.project_id == test_project_id

    # on create, Gate does not give back a presigned url, need to request it.
    f: File = await api_client.get_file(new_file.id)
    assert f.presigned_download_url is not None

    async with httpx.AsyncClient() as plain_client:
        resp = await plain_client.get(f.presigned_download_url)
        assert resp.status_code == 200
        assert resp.content == content

    # Delete file
    deleted_file = await api_client.delete_file(new_file.id)
    assert deleted_file.id == new_file.id
    assert deleted_file.deleted_at is not None


async def test_get_file_version(api_client: APIClient, notebook_maker):
    f: File = await notebook_maker()
    versions = await api_client.get_file_versions(f.id)
    assert len(versions) == 1
    assert versions[0].file_id == f.id
    # The three key fields are id (version id), number, and presigned url to download content
    assert versions[0].id is not None
    assert versions[0].number == 0
    assert versions[0].content_presigned_url is not None

    # Trigger a version save -- something needs to change (i.e. make a delta) or save as named
    endpoint = f"/v1/files/{f.id}/versions"
    resp = await api_client.client.post(endpoint, json={"name": "foo"})
    assert resp.status_code == 201

    new_versions = await api_client.get_file_versions(f.id)
    assert new_versions[0].number == 1

    assert len(new_versions) == 2

    assert len(new_versions) == 2

    assert len(new_versions) == 2
