import json
import re
from pathlib import Path
from urllib.parse import unquote_plus

import httpx
import pytest

from osm_tags_to_object.checkpoint import Checkpoint, FileCheckpointStore
from osm_tags_to_object.client import OverpassClient
from osm_tags_to_object.planet import fetch_planet
from osm_tags_to_object.retry import RetryConfig
from osm_tags_to_object.tiles import TileGrid


def _make_client(per_tile_payloads: dict[str, dict]) -> tuple[OverpassClient, list[str]]:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = unquote_plus(request.content.decode())
        m = re.search(r"\(([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+)\)", body)
        if m is None:
            key = "PLANET"
        else:
            s, w, n, e = m.groups()
            key = f"tile_{float(s):.6f}_{float(w):.6f}_{float(n):.6f}_{float(e):.6f}"
        seen.append(key)
        payload = per_tile_payloads.get(key, {"elements": []})
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = OverpassClient(
        http_client=httpx.Client(transport=transport),
        retry_config=RetryConfig(max_attempts=1),
        sleep=lambda _: None,
    )
    return client, seen


def test_fetch_planet_yields_objects_from_every_tile(tmp_path: Path):
    payloads = {
        "tile_43.000000_7.000000_43.500000_7.500000": {
            "elements": [
                {
                    "type": "way",
                    "id": 1,
                    "tags": {"amenity": "bench"},
                    "geometry": [{"lat": 43.1, "lon": 7.1}, {"lat": 43.2, "lon": 7.2}],
                }
            ]
        },
        "tile_43.500000_7.000000_44.000000_7.500000": {
            "elements": [
                {
                    "type": "way",
                    "id": 2,
                    "tags": {"amenity": "fountain"},
                    "geometry": [{"lat": 43.6, "lon": 7.1}, {"lat": 43.7, "lon": 7.2}],
                }
            ]
        },
    }
    client, seen = _make_client(payloads)
    cp = Checkpoint(FileCheckpointStore(tmp_path / "cp.json"))

    bbox = (43.0, 7.0, 44.0, 8.0)
    objects = list(
        fetch_planet(
            {"amenity": ["bench", "fountain"]},
            bbox,
            cp,
            tile_rows=2,
            tile_cols=2,
            client=client,
        )
    )

    assert len(objects) == 2
    assert {o.id for o in objects} == {1, 2}
    assert len(seen) == 4


def test_fetch_planet_skips_already_completed_tiles(tmp_path: Path):
    client, seen = _make_client({})
    cp = Checkpoint(FileCheckpointStore(tmp_path / "cp.json"))

    tiles = list(TileGrid((43.0, 7.0, 44.0, 8.0), rows=2, cols=2))
    cp.mark_done(tiles[0].key)
    cp.mark_done(tiles[1].key)

    bbox = (43.0, 7.0, 44.0, 8.0)
    list(
        fetch_planet(
            {"amenity": "bench"},
            bbox,
            cp,
            tile_rows=2,
            tile_cols=2,
            client=client,
        )
    )

    assert len(seen) == 2


def test_fetch_planet_persists_progress_to_disk(tmp_path: Path):
    cp_path = tmp_path / "cp.json"

    first_attempt = {"n": 0}

    def first_success_then_500(request: httpx.Request) -> httpx.Response:
        first_attempt["n"] += 1
        if first_attempt["n"] == 1:
            return httpx.Response(200, json={"elements": []})
        return httpx.Response(500, text="boom")

    client = OverpassClient(
        http_client=httpx.Client(transport=httpx.MockTransport(first_success_then_500)),
        retry_config=RetryConfig(max_attempts=1),
        sleep=lambda _: None,
    )
    cp = Checkpoint(FileCheckpointStore(cp_path))
    bbox = (43.0, 7.0, 44.0, 8.0)
    with pytest.raises(httpx.HTTPStatusError):
        list(
            fetch_planet(
                {"amenity": "bench"},
                bbox,
                cp,
                tile_rows=2,
                tile_cols=2,
                client=client,
            )
        )
    client.close()

    persisted = json.loads(cp_path.read_text())
    assert len(persisted) == 1

    client2, seen2 = _make_client({})
    cp2 = Checkpoint(FileCheckpointStore(cp_path))
    list(
        fetch_planet(
            {"amenity": "bench"}, bbox, cp2, tile_rows=2, tile_cols=2, client=client2
        )
    )
    client2.close()

    assert len(seen2) == 3


def test_fetch_planet_marks_tile_done_even_when_it_returns_no_objects(tmp_path: Path):
    cp_path = tmp_path / "cp.json"
    client, _ = _make_client({})
    cp = Checkpoint(FileCheckpointStore(cp_path))
    bbox = (43.0, 7.0, 44.0, 8.0)
    list(
        fetch_planet(
            {"amenity": "bench"}, bbox, cp, tile_rows=1, tile_cols=1, client=client
        )
    )
    client.close()

    fresh = Checkpoint(FileCheckpointStore(cp_path))
    assert fresh.count == 1


def test_fetch_planet_does_not_swallow_exceptions_but_keeps_checkpoint_intact(tmp_path: Path):
    """If a tile fetch raises, prior tiles stay marked done; failing tile is NOT marked done."""
    attempt = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempt["n"] += 1
        if attempt["n"] == 1:
            return httpx.Response(200, json={"elements": []})
        return httpx.Response(500, text="boom")

    client = OverpassClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        retry_config=RetryConfig(max_attempts=1),
        sleep=lambda _: None,
    )
    cp = Checkpoint(FileCheckpointStore(tmp_path / "cp.json"))
    bbox = (43.0, 7.0, 44.0, 8.0)

    with pytest.raises(httpx.HTTPStatusError):
        list(
            fetch_planet(
                {"amenity": "bench"},
                bbox,
                cp,
                tile_rows=1,
                tile_cols=2,
                client=client,
            )
        )
    client.close()

    tiles = list(TileGrid(bbox, rows=1, cols=2))
    assert cp.is_done(tiles[0].key)
    assert not cp.is_done(tiles[1].key)
