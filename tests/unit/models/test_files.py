from datetime import datetime
from uuid import uuid4

from origami.models.api.files import File


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
