import os

import pytest


@pytest.fixture
def tmp_noteable_url_environ() -> str:
    orig_value = os.environ.get("PUBLIC_NOTEABLE_URL", "")

    new_value = "https://localhost/api"
    os.environ["PUBLIC_NOTEABLE_URL"] = new_value

    yield new_value

    os.environ["PUBLIC_NOTEABLE_URL"] = orig_value
