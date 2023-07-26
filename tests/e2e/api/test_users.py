from origami.clients.api import APIClient
from origami.models.api.users import User


async def test_users_me(api_client: APIClient) -> None:
    user: User = await api_client.user_info()
    assert isinstance(user, User)
    assert user.id is not None
