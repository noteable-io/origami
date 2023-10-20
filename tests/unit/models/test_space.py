from uuid import uuid4
from datetime import datetime

from origami.models.api.spaces import Space


class TestSpace:
    def test_construct_url(self, tmp_noteable_url_environ: str):
        space = Space(
            id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            name="MySpace",
            description="Where did Tom end up?",
        )

        assert space.url == f"{tmp_noteable_url_environ}/s/{space.id}"
