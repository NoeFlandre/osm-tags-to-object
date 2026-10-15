from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from .retry import RetryConfig, retry_with_backoff


class OverpassClient:
    """Thin HTTP client for the Overpass API.

    Wraps a single ``POST`` per call with :func:`retry_with_backoff` so the
    public Overpass instance's aggressive 429 / 503 rate limiting does not
    leak into the rest of the codebase.
    """

    DEFAULT_URL = "https://overpass-api.de/api/interpreter"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_USER_AGENT = "osm-tags-to-object/0.1 (https://github.com/NoeFlandre/osm-tags-to-object)"

    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        retry_config: RetryConfig = RetryConfig(),
        sleep: Callable[[float], None] = time.sleep,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        self._user_agent = user_agent
        self._retry_config = retry_config
        self._sleep = sleep
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)

    def fetch(self, query: str) -> dict[str, Any]:
        """POST an Overpass QL query and return the parsed JSON response."""
        return retry_with_backoff(
            lambda: self._fetch_once(query),
            config=self._retry_config,
            sleep=self._sleep,
        )

    def _fetch_once(self, query: str) -> dict[str, Any]:
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
