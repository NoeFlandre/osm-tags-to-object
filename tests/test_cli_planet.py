import json
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from osm_tags_to_object.cli import cli
from osm_tags_to_object.client import OverpassClient
from osm_tags_to_object.retry import RetryConfig


def _install_mock_overpass(monkeypatch, payloads: dict[str, dict]) -> None:
    def factory(*args, **kwargs):
        import re
        from urllib.parse import unquote_plus

        def handler(request: httpx.Request) -> httpx.Response:
            body = unquote_plus(request.content.decode())
            m = re.search(r"\(([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+)\)", body)
            if m is None:
                key = "PLANET"
            else:
                s, w, n, e = m.groups()
                key = f"tile_{float(s):.6f}_{float(w):.6f}_{float(n):.6f}_{float(e):.6f}"
            return httpx.Response(200, json=payloads.get(key, {"elements": []}))

        kwargs.setdefault("retry_config", RetryConfig(max_attempts=1))
        kwargs.setdefault("sleep", lambda _: None)
        kwargs["http_client"] = httpx.Client(transport=httpx.MockTransport(handler))
        return OverpassClient(*args, **kwargs)

    monkeypatch.setattr("osm_tags_to_object.cli.OverpassClient", factory)


def test_cli_planet_writes_geojson_and_checkpoint(monkeypatch, tmp_path: Path):
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
        }
    }
    _install_mock_overpass(monkeypatch, payloads)

    cp_path = tmp_path / "cp.json"
    out = tmp_path / "out.geojson"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "planet",
            "--tags",
            "amenity=bench",
            "--bbox",
            "43.0,7.0,44.0,8.0",
            "--tile-rows",
            "2",
            "--tile-cols",
            "2",
            "--checkpoint",
            str(cp_path),
            "-o",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["amenity"] == "bench"
    # All 4 tiles done after the run.
    persisted = json.loads(cp_path.read_text())
    assert len(persisted) == 4


def test_cli_planet_resumes_from_existing_checkpoint(monkeypatch, tmp_path: Path):
    cp_path = tmp_path / "cp.json"
    # Pre-seed the checkpoint as if 2 tiles are already done.
    cp_path.write_text(
        json.dumps(
            [
                "tile_43.000000_7.000000_43.500000_7.500000",
                "tile_43.000000_7.500000_43.500000_8.000000",
            ]
        )
    )

    # Mock returns one object for any un-done tile.
    payloads = {
        "tile_43.500000_7.000000_44.000000_7.500000": {
            "elements": [
                {
                    "type": "way",
                    "id": 99,
                    "tags": {"amenity": "fountain"},
                    "geometry": [{"lat": 43.6, "lon": 7.1}, {"lat": 43.7, "lon": 7.2}],
                }
            ]
        }
    }
    _install_mock_overpass(monkeypatch, payloads)

    out = tmp_path / "out.geojson"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "planet",
            "--tags",
            "amenity=fountain",
            "--bbox",
            "43.0,7.0,44.0,8.0",
            "--tile-rows",
            "2",
            "--tile-cols",
            "2",
            "--checkpoint",
            str(cp_path),
            "-o",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    # Only the one previously-un-done tile produced an object.
    assert len(data["features"]) == 1
    assert data["features"][0]["id"] == 99


def test_cli_planet_rejects_invalid_bbox(monkeypatch, tmp_path: Path):
    def fail(*_a, **_kw):
        raise AssertionError("OverpassClient should not be instantiated on bad input")

    monkeypatch.setattr("osm_tags_to_object.cli.OverpassClient", fail)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "planet",
            "--tags",
            "amenity=bench",
            "--bbox",
            "43.0,7.0",
            "--checkpoint",
            str(tmp_path / "cp.json"),
            "-o",
            str(tmp_path / "out.geojson"),
        ],
    )
    assert result.exit_code != 0
    assert "bbox" in str(result.exception).lower()
