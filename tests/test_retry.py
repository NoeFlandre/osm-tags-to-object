import httpx

from osm_tags_to_object.retry import RetryConfig, retry_with_backoff


def _http_error(status: int, headers: dict | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://overpass-api.de/api/interpreter")
    response = httpx.Response(status, headers=headers or {})
    return httpx.HTTPStatusError("boom", request=request, response=response)


def test_retry_returns_immediately_when_call_succeeds():
    calls = []

    def op():
        calls.append(1)
        return "ok"

    result = retry_with_backoff(op, sleep=lambda _: None)
    assert result == "ok"
    assert len(calls) == 1


def test_retry_succeeds_after_a_transient_429():
    calls = []

    def op():
        calls.append(1)
        if len(calls) < 2:
            raise _http_error(429)
        return "ok"

    result = retry_with_backoff(op, sleep=lambda _: None)
    assert result == "ok"
    assert len(calls) == 2


def test_retry_does_not_retry_on_non_transient_4xx():
    calls = []

    def op():
        calls.append(1)
        raise _http_error(404)

    try:
        retry_with_backoff(op, sleep=lambda _: None)
    except httpx.HTTPStatusError:
        pass
    assert len(calls) == 1


def test_retry_uses_exponential_backoff_between_attempts():
    sleeps: list[float] = []

    def op():
        raise _http_error(503)

    try:
        retry_with_backoff(
            op,
            config=RetryConfig(max_attempts=4, base_delay=1.0, backoff_factor=2.0),
            sleep=sleeps.append,
        )
    except httpx.HTTPStatusError:
        pass
    # delays between attempts 1->2, 2->3, 3->4
    assert sleeps == [1.0, 2.0, 4.0]


def test_retry_caps_delay_at_max_delay():
    sleeps: list[float] = []

    def op():
        raise _http_error(503)

    try:
        retry_with_backoff(
            op,
            config=RetryConfig(
                max_attempts=5, base_delay=10.0, backoff_factor=2.0, max_delay=15.0
            ),
            sleep=sleeps.append,
        )
    except httpx.HTTPStatusError:
        pass
    # 10, 15 (capped), 15 (capped), 15 (capped)
    assert sleeps == [10.0, 15.0, 15.0, 15.0]


def test_retry_gives_up_after_max_attempts():
    calls = []

    def op():
        calls.append(1)
        raise _http_error(503)

    try:
        retry_with_backoff(
            op, config=RetryConfig(max_attempts=3), sleep=lambda _: None
        )
    except httpx.HTTPStatusError:
        pass
    assert len(calls) == 3


def test_retry_respects_retry_after_header_on_429():
    sleeps: list[float] = []

    def op():
        raise _http_error(429, headers={"Retry-After": "7"})

    try:
        retry_with_backoff(
            op,
            config=RetryConfig(max_attempts=2),
            sleep=sleeps.append,
        )
    except httpx.HTTPStatusError:
        pass
    assert sleeps == [7.0]


def test_retry_retries_on_network_errors():
    calls = []

    def op():
        calls.append(1)
        if len(calls) < 2:
            raise httpx.ConnectError("connection refused")
        return "ok"

    result = retry_with_backoff(op, sleep=lambda _: None)
    assert result == "ok"
    assert len(calls) == 2
