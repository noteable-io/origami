from typing import Optional

import httpx

from origami.defs.models import User


class GateAPIClient:
    def __init__(
        self,
        api_base_url: str,
        authorization_token: str,
        headers: Optional[dict] = None,
        transport: Optional[httpx.AsyncHTTPTransport] = None,
        timeout: httpx.Timeout = httpx.Timeout(5.0),
    ):
        # jwt and api_base_url saved as attributes because they're re-used when creating rtu client
        self.jwt = authorization_token
        self.api_base_url = api_base_url
        self.headers = {"Authorization": f"Bearer {self.jwt}"}
        if headers:
            self.headers.update(headers)

        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            headers=self.headers,
            transport=transport,
            timeout=timeout,
        )

    def add_tags_and_contextvars(self, **tags):
        """Hook for Apps to override so they can set structlog contextvars or trace tags"""
        pass

    async def user_info(self) -> User:
        """Get the current user's info"""
        endpoint = "/users/me"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        user = User.parse_obj(resp.json())
        self.add_tags_and_contextvars(user_id=str(user.id))
        return user
