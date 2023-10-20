from datetime import datetime
from uuid import uuid4

from origami.models.api.projects import Project


class TestProject:
    def test_construct_url(self, tmp_noteable_url_environ: str):
        project = Project(
            id=uuid4(),
            space_id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            name="My Project",
            description="Describe",
        )

        assert project.url == f"{tmp_noteable_url_environ}/p/{project.id}"
