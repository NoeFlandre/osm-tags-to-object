from __future__ import annotations

from typing import Any

import httpx


class OverpassClient:
    """Thin HTTP client for the Overpass API."""

    DEFAULT_URL = "https://overpass-api.de/api/interpreter"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_USER_AGENT = "osm-tags-to-object/0.1 (https://github.com/NoeFlandre/osm-tags-to-object)"

    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        self._user_agent = user_agent
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)

    def fetch(self, query: str) -> dict[str, Any]:
        """POST an Overpass QL query and return the parsed JSON response."""
        response = self._client.post(
            self._url,
            data={"data": query},
            headers={
                "Accept": "application/json",
                "User-Agent": self._user_agent,
            },
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OverpassClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
