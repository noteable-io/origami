from typing import Optional

import httpx


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


httpx.ti
