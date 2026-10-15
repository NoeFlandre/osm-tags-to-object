import json
from pathlib import Path

import httpx
from click.testing import CliRunner

from osm_tags_to_object.cli import cli
from osm_tags_to_object.client import OverpassClient
from osm_tags_to_object.retry import RetryConfig


def _install_mock_overpass(monkeypatch, payload: dict) -> None:
    def factory(*args, **kwargs):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)
        kwargs.setdefault("retry_config", RetryConfig(max_attempts=2))
        kwargs.setdefault("sleep", lambda _: None)
        kwargs["http_client"] = httpx.Client(transport=httpx.MockTransport(handler))
        return OverpassClient(*args, **kwargs)

    monkeypatch.setattr("osm_tags_to_object.cli.OverpassClient", factory)


def test_cli_fetch_writes_geojson_file(monkeypatch, tmp_path: Path):
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"amenity": "bench"},
                "geometry": [
                    {"lat": 43.73, "lon": 7.42},
                    {"lat": 43.74, "lon": 7.43},
                    {"lat": 43.75, "lon": 7.44},
                ],
            }
        ]
    }
    _install_mock_overpass(monkeypatch, payload)

    out = tmp_path / "out.geojson"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "fetch",
            "--tags",
            "amenity=bench",
            "--bbox",
            "43.7,7.4,43.8,7.5",
            "-o",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["amenity"] == "bench"


def test_cli_fetch_rejects_invalid_bbox(monkeypatch, tmp_path: Path):
    def fail(*_a, **_kw):
        raise AssertionError("OverpassClient should not be instantiated on bad input")

    monkeypatch.setattr("osm_tags_to_object.cli.OverpassClient", fail)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["fetch", "--tags", "amenity=bench", "--bbox", "43.7,7.4", "-o", str(tmp_path / "x.geojson")],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "bbox" in str(result.exception).lower()


def test_cli_map_renders_an_html_file(tmp_path: Path):
    geojson = tmp_path / "in.geojson"
    geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": 1,
                        "osm_type": "way",
                        "properties": {"amenity": "bench"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[7.0, 43.0], [7.1, 43.0], [7.1, 43.1], [7.0, 43.1], [7.0, 43.0]]
                            ],
                        },
                    }
                ],
            }
        )
    )
    html = tmp_path / "out.html"
    runner = CliRunner()
    result = runner.invoke(cli, ["map", "-i", str(geojson), "-o", str(html)])
    assert result.exit_code == 0, result.output
    assert html.exists()
    assert "leaflet" in html.read_text().lower()
