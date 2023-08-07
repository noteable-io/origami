import logging
import os
import uuid
from typing import List, Literal, Optional, Union

import httpx
import pydantic

from origami.clients.rtu import RTUClient
from origami.models.api.datasources import DataSource
from origami.models.api.files import File
from origami.models.api.outputs import KernelOutputCollection
from origami.models.api.projects import Project
from origami.models.api.spaces import Space
from origami.models.api.users import User
from origami.models.kernels import KernelSession
from origami.models.notebook import Notebook
from origami.notebook.builder import NotebookBuilder

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(
        self,
        authorization_token: str,
        api_base_url: str = "https://app.noteable.io/gate/api",
        headers: Optional[dict] = None,
        transport: Optional[httpx.AsyncHTTPTransport] = None,
        timeout: httpx.Timeout = httpx.Timeout(5.0),
        rtu_client_type: str = 'origami',
    ):
        # jwt and api_base_url saved as attributes because they're re-used when creating rtu client
        self.jwt = authorization_token
        self.api_base_url = os.environ.get('NOTEABLE_API_URL', api_base_url)
        self.headers = {"Authorization": f"Bearer {self.jwt}"}
        if headers:
            self.headers.update(headers)

        self.client = httpx.AsyncClient(
            base_url=self.api_base_url,
            headers=self.headers,
            transport=transport,
            timeout=timeout,
        )
        # Hack until Gate changes out rtu_client_type from enum to str
        if rtu_client_type not in ['origami', 'origamist', 'planar_ally', 'geas']:
            rtu_client_type = 'unknown'
        self.rtu_client_type = rtu_client_type  # Only used when generating an RTUClient

    def add_tags_and_contextvars(self, **tags):
        """Hook for Apps to override so they can set structlog contextvars or ddtrace tags etc"""
        pass

    async def user_info(self) -> User:
        """Get email and other info for User account of this Client's JWT."""
        endpoint = "/users/me"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        user = User.parse_obj(resp.json())
        self.add_tags_and_contextvars(user_id=str(user.id))
        return user

    # Spaces are collections of Projects. Some "scoped" resources such as Secrets and Datasources
    # can also be attached to a Space and made available to all users of that Space.
    async def create_space(self, name: str, description: Optional[str] = None) -> Space:
        endpoint = "/spaces"
        resp = await self.client.post(endpoint, json={"name": name, "description": description})
        resp.raise_for_status()
        space = Space.parse_obj(resp.json())
        self.add_tags_and_contextvars(space_id=str(space.id))
        return space

    async def get_space(self, space_id: uuid.UUID) -> Space:
        self.add_tags_and_contextvars(space_id=str(space_id))
        endpoint = f"/spaces/{space_id}"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        space = Space.parse_obj(resp.json())
        return space

    async def delete_space(self, space_id: uuid.UUID) -> Space:
        self.add_tags_and_contextvars(space_id=str(space_id))
        endpoint = f"/spaces/{space_id}"
        resp = await self.client.delete(endpoint)
        resp.raise_for_status()
        space = Space.parse_obj(resp.json())
        return space

    async def list_space_projects(self, space_id: uuid.UUID) -> List[Project]:
        """List all Projects in a Space."""
        self.add_tags_and_contextvars(space_id=str(space_id))
        endpoint = f"/spaces/{space_id}/projects"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        projects = [Project.parse_obj(project) for project in resp.json()]
        return projects

    # Projects are collections of Files, including Notebooks. When a Kernel is launched for a
    # Notebook, all Files in the Project are volume mounted into the Kernel container at startup.
    async def create_project(
        self, space_id: uuid.UUID, name: str, description: Optional[str] = None
    ) -> Project:
        self.add_tags_and_contextvars(space_id=str(space_id))
        endpoint = "/projects"
        resp = await self.client.post(
            endpoint, json={'space_id': str(space_id), "name": name, "description": description}
        )
        resp.raise_for_status()
        project = Project.parse_obj(resp.json())
        self.add_tags_and_contextvars(project_id=str(project.id))
        return project

    async def get_project(self, project_id: uuid.UUID) -> Project:
        self.add_tags_and_contextvars(project_id=str(project_id))
        endpoint = f"/projects/{project_id}"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        project = Project.parse_obj(resp.json())
        return project

    async def delete_project(self, project_id: uuid.UUID) -> Project:
        self.add_tags_and_contextvars(project_id=str(project_id))
        endpoint = f"/projects/{project_id}"
        resp = await self.client.delete(endpoint)
        resp.raise_for_status()
        project = Project.parse_obj(resp.json())
        return project

    async def list_project_files(self, project_id: uuid.UUID) -> List[File]:
        """List all Files in a Project. Files do not have presigned download urls included here."""
        self.add_tags_and_contextvars(project_id=str(project_id))
        endpoint = f'/projects/{project_id}/files'
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        files = [File.parse_obj(file) for file in resp.json()]
        return files

    # Files are flat files (like text, csv, etc) or Notebooks.
    async def _multi_step_file_create(
        self,
        project_id: uuid.UUID,
        path: str,
        file_type: Literal['file', 'notebook'],
        content: bytes,
    ) -> File:
        # Uploading files using the /v1/files endpoint is a multi-step process.
        # 1. POST /v1/files to get a presigned upload url and file id
        # 2. PUT the file content to the presigned upload url, save the etag
        # 3. POST /v1/files/{file-id}/complete-upload with upload id / key / etag
        # file_type is 'file' for all non-Notebook files, and 'notebook' for Notebooks
        # (1) Reserve File in db
        body = {
            "project_id": str(project_id),
            "path": path,
            "type": file_type,
            'file_size_bytes': len(content),
        }
        resp = await self.client.post("/v1/files", json=body)
        resp.raise_for_status()

        # (1.5) parse response
        js = resp.json()
        upload_url = js["presigned_upload_url_info"]["parts"][0]["upload_url"]
        upload_id = js["presigned_upload_url_info"]["upload_id"]
        upload_key = js["presigned_upload_url_info"]["key"]
        file = File.parse_obj(js)

        # (2) Upload to pre-signed url
        # TODO: remove this hack if/when we get containers in Skaffold to be able to translate
        # localhost urls to the minio pod/container
        if 'LOCAL_K8S' in os.environ and bool(os.environ['LOCAL_K8S']):
            upload_url = upload_url.replace('localhost', 'minio')
        async with httpx.AsyncClient() as plain_client:
            r = await plain_client.put(upload_url, content=content)
            r.raise_for_status()

        # (3) Tell API we finished uploading (returns 204)
        etag = r.headers["etag"].strip('"')
        body = {
            "upload_id": upload_id,
            "key": upload_key,
            "parts": [{"etag": etag, "part_number": 1}],
        }
        endpoint = f"/v1/files/{file.id}/complete-upload"
        r2 = await self.client.post(endpoint, json=body)
        r2.raise_for_status()
        return file

    async def create_file(self, project_id: uuid.UUID, path: str, content: bytes) -> File:
        """Create a non-Notebook File in a Project"""
        self.add_tags_and_contextvars(project_id=str(project_id))
        file = await self._multi_step_file_create(project_id, path, "file", content)
        self.add_tags_and_contextvars(file_id=str(file.id))
        logger.info("Created new file", extra={"file_id": str(file.id)})
        return file

    async def create_notebook(
        self, project_id: uuid.UUID, path: str, notebook: Optional[Notebook] = None
    ) -> File:
        """Create a Notebook in a Project"""
        self.add_tags_and_contextvars(project_id=str(project_id))
        if notebook is None:
            notebook = Notebook()
        content = notebook.json().encode()
        file = await self._multi_step_file_create(project_id, path, "notebook", content)
        self.add_tags_and_contextvars(file_id=str(file.id))
        logger.info("Created new notebook", extra={"file_id": str(file.id)})
        return file

    async def get_file(self, file_id: uuid.UUID) -> File:
        """Get metadata about a File, not including its content. Includes presigned download url."""
        self.add_tags_and_contextvars(file_id=str(file_id))
        endpoint = f'/v1/files/{file_id}'
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        file = File.parse_obj(resp.json())
        return file

    async def get_file_content(self, file_id: uuid.UUID) -> bytes:
        """Get the content of a File, including Notebooks."""
        self.add_tags_and_contextvars(file_id=str(file_id))
        file = await self.get_file(file_id)
        presigned_download_url = file.presigned_download_url
        if not presigned_download_url:
            raise ValueError(f"File {file.id} does not have a presigned download url")
        # TODO: remove this hack if/when we get containers in Skaffold to be able to translate
        # localhost urls to the minio pod/container
        if 'LOCAL_K8S' in os.environ and bool(os.environ['LOCAL_K8S']):
            presigned_download_url = presigned_download_url.replace('localhost', 'minio')
        async with httpx.AsyncClient() as plain_http_client:
            resp = await plain_http_client.get(presigned_download_url)
            resp.raise_for_status()
        return resp.content

    async def delete_file(self, file_id: uuid.UUID) -> File:
        self.add_tags_and_contextvars(file_id=str(file_id))
        endpoint = f'/v1/files/{file_id}'
        resp = await self.client.delete(endpoint)
        resp.raise_for_status()
        file = File.parse_obj(resp.json())
        return file

    async def get_datasources_for_notebook(self, file_id: uuid.UUID) -> List[DataSource]:
        """Return a list of Datasources that can be used in SQL cells within a Notebook"""
        self.add_tags_and_contextvars(file_id=str(file_id))
        endpoint = f"/v1/datasources/by_notebook/{file_id}"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        datasources = pydantic.parse_obj_as(List[DataSource], resp.json())

        return datasources

    async def launch_kernel(
        self, file_id: uuid.UUID, kernel_name: str = 'python3', hardware_size: str = 'small'
    ) -> KernelSession:
        endpoint = '/v1/sessions'
        data = {
            'file_id': str(file_id),
            'kernel_config': {
                'kernel_name': kernel_name,
                'hardware_size_identifier': hardware_size,
            },
        }
        resp = await self.client.post(endpoint, json=data)
        resp.raise_for_status()
        kernel_session = KernelSession.parse_obj(resp.json())
        self.add_tags_and_contextvars(kernel_session_id=str(kernel_session.id))
        logger.info(
            "Launched new kernel",
            extra={"kernel_session_id": str(kernel_session.id), "file_id": str(file_id)},
        )
        return kernel_session

    async def shutdown_kernel(self, kernel_session_id: uuid.UUID) -> None:
        endpoint = f'/sessions/{kernel_session_id}'
        resp = await self.client.delete(endpoint, timeout=60)
        resp.raise_for_status()
        logger.info("Shut down kernel", extra={"kernel_session_id": str(kernel_session_id)})

    async def get_output_collection(
        self, output_collection_id: uuid.UUID
    ) -> KernelOutputCollection:
        endpoint = f'/outputs/collection/{output_collection_id}'
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        return KernelOutputCollection.parse_obj(resp.json())

    async def connect_realtime(self, file: Union[File, uuid.UUID, str]) -> RTUClient:
        """
        Create an RTUClient for a Notebook by file id. This will perform the following steps:
         - Check /v1/files to get the current version information and presigned download url
         - Download seed notebook and create a NotebookBuilder from it
         - Create an RTUClient, initialize the websocket connection, authenticate, and subscribe
         - Apply delts to in-memory NotebookBuilder
        """
        file_id = None

        if isinstance(file, str):
            file_id = uuid.UUID(file)
        elif isinstance(file, uuid.UUID):
            file_id = file
        elif isinstance(file, File):
            file_id = file.id
        else:
            raise ValueError(f"Must provide a `file_id` or a File, not {file}")

        self.add_tags_and_contextvars(file_id=str(file_id))

        logger.info(f"Creating RTUClient for file {file_id}")
        file = await self.get_file(file_id)
        if file.type != 'notebook':
            raise ValueError(f"File {file_id} is not a notebook")
        if not file.presigned_download_url:
            raise ValueError(f"File {file_id} does not have a presigned download url")
        # TODO: remove this hack if/when we get containers in Skaffold to be able to translate
        # localhost urls to the minio pod/container
        if 'LOCAL_K8S' in os.environ and bool(os.environ['LOCAL_K8S']):
            file.presigned_download_url = file.presigned_download_url.replace('localhost', 'minio')
        async with httpx.AsyncClient() as plain_http_client:
            resp = await plain_http_client.get(file.presigned_download_url)
            resp.raise_for_status()

        seed_notebook = Notebook.parse_obj(resp.json())
        nb_builder = NotebookBuilder(seed_notebook=seed_notebook)
        rtu_url = self.api_base_url.replace('http', 'ws') + '/v1/rtu'
        rtu_client = RTUClient(
            rtu_url=rtu_url,
            jwt=self.jwt,
            file_id=file.id,
            file_version_id=file.current_version_id,
            builder=nb_builder,
            rtu_client_type=self.rtu_client_type,
        )
        await rtu_client.initialize()
        await rtu_client.deltas_to_apply_event.wait()
        return rtu_client
