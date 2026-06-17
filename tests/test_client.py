import httpx

from osm_tags_to_object.client import OverpassClient


def test_client_posts_query_to_endpoint_and_returns_json():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"elements": [{"type": "way", "id": 1, "tags": {"amenity": "bench"}}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = OverpassClient(http_client=http_client)
        result = client.fetch('way["amenity"="bench"];')

    assert captured["method"] == "POST"
    assert "overpass" in captured["url"]
    assert captured["body"] == 'data=way%5B%22amenity%22%3D%22bench%22%5D%3B'
    assert result == {
        "elements": [{"type": "way", "id": 1, "tags": {"amenity": "bench"}}]
    }


def test_client_sets_accept_header_to_json():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"elements": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = OverpassClient(http_client=http_client)
        client.fetch("out;")

    # Overpass API rejects `Accept: */*` with 406, so we must be explicit.
    assert captured["headers"]["accept"] == "application/json"


def test_client_sets_a_descriptive_user_agent():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["user-agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={"elements": []})

    transport = httpx.MockTransport(handler)
    # No http_client passed -> client builds its own with the configured UA.
    client = OverpassClient(http_client=httpx.Client(transport=transport))
    client.fetch("out;")
    client.close()

    # The default python-httpx User-Agent is rejected by Overpass (HTTP 406).
    ua = captured["user-agent"]
    assert ua
    assert "python-httpx" not in ua
    assert "osm-tags-to-object" in ua


def test_client_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = OverpassClient(http_client=http_client)
        try:
            client.fetch("way[amenity=bench];")
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 429
        else:
            raise AssertionError("expected HTTPStatusError")
