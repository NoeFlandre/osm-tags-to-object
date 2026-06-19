from urllib.parse import unquote_plus

import httpx

from osm_tags_to_object.client import OverpassClient
from osm_tags_to_object.pipeline import fetch_matching_objects
from osm_tags_to_object.tags import TagFilter


def _mock_overpass(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)
    return httpx.MockTransport(handler)


def test_pipeline_filters_out_nodes_and_returns_only_ways_and_relations():
    payload = {
        "elements": [
            {"type": "node", "id": 1, "tags": {"amenity": "bench"}},
            {"type": "way", "id": 2, "tags": {"amenity": "bench"}, "nodes": [10, 11]},
            {
                "type": "relation",
                "id": 3,
                "tags": {"type": "multipolygon", "amenity": "bench"},
                "members": [{"type": "way", "ref": 2, "role": "outer"}],
            },
        ]
    }
    with httpx.Client(transport=_mock_overpass(payload)) as http_client:
        client = OverpassClient(http_client=http_client)
        objects = fetch_matching_objects(
            TagFilter({"amenity": "bench"}),
            client=client,
        )

    types = [obj.type for obj in objects]
    assert types == ["way", "relation"]
    assert [obj.id for obj in objects] == [2, 3]


def test_pipeline_sends_query_with_bbox_when_provided():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"elements": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = OverpassClient(http_client=http_client)
        fetch_matching_objects(
            TagFilter({"amenity": "bench"}),
            bbox=(43.7, 7.4, 43.8, 7.5),
            client=client,
        )

    decoded = unquote_plus(captured["body"])
    assert "(43.7,7.4,43.8,7.5)" in decoded
