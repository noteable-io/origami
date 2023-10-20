from uuid import uuid4
import os
from datetime import datetime

import pytest

from origami.models.api.files import File


@pytest.fixture
def tmp_noteable_url_environ() -> str:
    orig_value = os.environ.get("PUBLIC_NOTEABLE_URL", "")

    new_value = "https://localhost/api"
    os.environ["PUBLIC_NOTEABLE_URL"] = new_value

    yield new_value

    os.environ["PUBLIC_NOTEABLE_URL"] = orig_value


class TestFile:
    def test_construct_url(self, tmp_noteable_url_environ: str):
        file = File(
            id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            filename="foo.txt",
            path="/etc/foo.txt",
            project_id=uuid4(),
            space_id=uuid4(),
            size=12,
            mimetype="text/plain",
            type="file",
            current_version_id=uuid4(),
            presigned_download_url="https://foo.bar/blat",
        )

        assert file.url == f"{tmp_noteable_url_environ}/f/{file.id}/{file.path}"
