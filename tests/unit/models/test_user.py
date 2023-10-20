import os
from datetime import datetime
from uuid import uuid4

from origami.models.api.users import User


class TestUser:
    def test_construct_auth_type(self):
        user = User(
            id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            handle="joe",
            email="joe@sample.com",
            first_name="Joe",
            last_name="Sample",
            origamist_default_project_id=uuid4(),
            principal_sub="oauth|456fdghdfdfgj",
        )

        assert user.auth_type == "oauth"
