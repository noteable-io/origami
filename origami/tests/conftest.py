import uuid
from datetime import datetime, timezone

import nbformat
import pytest

from origami.defs.access_levels import Visibility
from origami.defs.files import FileType, NotebookFile


@pytest.fixture
def file_content():
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("1 + 1") for _ in range(10)])


@pytest.fixture
def file(file_content):
    project_id = uuid.uuid4()
    return NotebookFile(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        project_id=project_id,
        filename="hello world.ipynb",
        path="folder/hello world.ipynb",
        type=FileType.notebook,
        created_by_id=uuid.uuid4(),
        visibility=Visibility.private,
        is_playground_mode_file=False,
        space_id=uuid.uuid4(),
        file_store_path=f"{project_id}/folder/hello world.ipynb",
        content=file_content,
    )
