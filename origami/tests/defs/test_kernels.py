import uuid
from datetime import datetime, timezone

import pytest

from origami.defs.access_levels import Visibility
from origami.defs.files import FileType, NotebookFile
from origami.defs.kernels import SessionRequestDetails


@pytest.fixture()
def file():
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
        content={"metadata": {}},
    )


class TestSessionRequestDetails:
    def test_generate_file_request(self, file):
        session_request = SessionRequestDetails.generate_file_request(file)
        assert session_request.file_id == file.id
        assert session_request.kernel_config.kernel_name == 'python3'
        assert session_request.kernel_config.hardware_size_identifier is None

    def test_generate_file_request_with_metadata(self, file):
        file = file.copy(
            update={
                "content": {
                    "metadata": {
                        "kernel_info": {
                            "name": "r",
                        },
                        "selected_hardware_size": "small",
                    }
                }
            }
        )
        session_request = SessionRequestDetails.generate_file_request(file)

        assert session_request.kernel_config.kernel_name == 'r'
        assert session_request.kernel_config.hardware_size_identifier == 'small'
