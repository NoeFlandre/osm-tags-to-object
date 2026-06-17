"""Retry helper with exponential backoff and Retry-After support.

Used by :class:`osm_tags_to_object.client.OverpassClient` to survive the
public Overpass instance's aggressive 429 / 503 rate limiting without
leaking that concern into the rest of the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

import httpx

T = TypeVar("T")

DEFAULT_TRANSIENT_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)
DEFAULT_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.NetworkError,
)


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    transient_status: tuple[int, ...] = DEFAULT_TRANSIENT_STATUS
    transient_exceptions: tuple[type[Exception], ...] = DEFAULT_TRANSIENT_EXCEPTIONS


def retry_with_backoff(
    op: Callable[[], T],
    config: RetryConfig = RetryConfig(),
    sleep: Callable[[float], None] = __import__("time").sleep,
) -> T:
    """Call ``op`` until it succeeds or non-transient errors are seen.

    On transient errors (configurable HTTP statuses and network exceptions),
    waits with exponential backoff and tries again up to ``config.max_attempts``.
    A ``Retry-After`` response header on a 429 overrides the computed delay.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return op()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in config.transient_status or attempt >= config.max_attempts:
                raise
            sleep(_delay(exc, attempt, config))
        except config.transient_exceptions:  # type: ignore[misc]
            if attempt >= config.max_attempts:
                raise
            sleep(_delay(None, attempt, config))


def _delay(
    exc: httpx.HTTPStatusError | None,
    attempt: int,
    config: RetryConfig,
) -> float:
    if exc is not None and exc.response.status_code == 429:
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), config.max_delay)
            except ValueError:
                pass  # HTTP-date format; fall back to backoff
    backoff = config.base_delay * (config.backoff_factor ** (attempt - 1))
    return min(backoff, config.max_delay)
