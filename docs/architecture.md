# Architecture

End-to-end data flow, the data model, and where to plug in new behaviour.

## High-level data flow

```
                       ┌─────────────────────────────────────────────────────────┐
                       │                       Overpass API                       │
                       └─────────────────────────────────────────────────────────┘
                                                  │
                                                  │ POST /api/interpreter  (Overpass QL)
                                                  │ Accept: application/json
                                                  │ User-Agent: osm-tags-to-object/0.1
                                                  ▼
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│ TagFilter  │ →  │ Overpass   │ →  │ Overpass   │ →  │ parser.py  │
│            │    │ query.py   │    │ client.py  │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
   {key:value}      Overpass QL      HTTP + retry     list[OSMObject]
                                       │
                                       ▼
                                  ┌────────────┐
                                  │ retry.py   │
                                  └────────────┘
                                       │
                                       ▼ (single fetch)
                                ┌─────────────────┐
                                │ pipeline.py     │  fetch_matching_objects()
                                │ fetch_matching  │  in-memory list
                                │ _objects        │
                                └─────────────────┘
                                       │
                                       ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
   │ tiles.py    │→ │ checkpoint  │→ │ planet.py       │  fetch_planet() yields
   │ TileGrid    │  │ .py         │  │ fetch_planet    │  objects tile-by-tile
   └─────────────┘  └─────────────┘  └─────────────────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │ storage.py   │  write_objects(iter, path, fmt)
                                          │ write_objects│
                                          └──────────────┘
                                                 │
                                ┌────────────────┴───────────────┐
                                ▼                                ▼
                       ┌─────────────────┐               ┌─────────────────┐
                       │ formats/        │               │ formats/        │
                       │ geojson.py      │               │ parquet.py      │
                       │ FeatureCollection│              │ ParquetWriter   │
                       └─────────────────┘               └─────────────────┘
                                │                                │
                                └────────────────┬───────────────┘
                                                 ▼
                                       ./data/*.geojson
                                       ./data/*.parquet

                            (one-off, not part of fetch)
                       ┌─────────────────────┐    ┌────────────┐
                       │ scripts/            │ →  │ map.py     │ → ./data/*.html
                       │ parquet_to_map_     │    │ render_map │
                       │ geojson.py          │    └────────────┘
                       └─────────────────────┘
                            ▲
                            │ reads large parquet, drops relations,
                            │ filters by bbox area, RDP-simplifies

                                                 ▼
                                          ┌──────────────┐
                                          │ hf sync      │
                                          │ (manual)     │
                                          └──────────────┘
                                                 ▼
                              hf://buckets/NoeFlandre/osm-tags-to-object
```

## Data model

```python
# frozen dataclass — see models.py
class OSMObject:
    type: str                            # "way" | "relation"
    id: int
    tags: dict[str, str]                 # flat key → string value
    geometry: tuple[tuple[float, float], ...]   # (lat, lon) tuples for ways
    members: tuple[dict, ...]            # relation member dicts (may carry geometry)
```

### Coordinate conventions

Three orders are in play. The code is explicit about each:

| Layer | Order | Notes |
|---|---|---|
| `OSMObject.geometry` | `(lat, lon)` tuples | internal canonical |
| Parquet `geometry` column | `{"lat": …, "lon": …}` structs | pyarrow `list<struct<lat:float64, lon:float64>>` |
| GeoJSON `coordinates` | `[lon, lat]` arrays | RFC 7946 |
| `folium.Polygon(location=…)` | `(lat, lon)` tuples | folium's reverse convention |

Conversions are in:
- `formats/geojson.py::_to_feature` (lat/lon → GeoJSON ring)
- `formats/parquet.py::_to_row` (OSMObject → parquet row)
- `map.py::compute_bounds` (GeoJSON → folium bounds)

## Parquet schema

Defined in `formats/parquet.py::_SCHEMA`:

| Column | Type | Notes |
|---|---|---|
| `type` | `string` | always `"way"` or `"relation"` |
| `id` | `int64` | OSM object id |
| `tags` | `map<string, string>` | OSM tags |
| `geometry` | `list<struct<lat: float64, lon: float64>>` | ways only; relations store geometry on members |
| `members_json` | `string` | JSON-encoded members for relations; `null` for ways |

Schema is a **public contract** for downstream readers (DuckDB, Spark, etc.).
Changing it requires a migration path.

## Module responsibilities

| Module | Owns | Does not own |
|---|---|---|
| `tags.py` | `TagFilter` shape | Overpass syntax, network, files |
| `query.py` | Overpass QL emission | HTTP, parsing, retries |
| `client.py` | HTTP + retry orchestration | parsing, writing, tiling |
| `parser.py` | JSON → `OSMObject` | query building, network |
| `models.py` | `OSMObject` shape | anything I/O |
| `pipeline.py` | single-area fetch pipeline | tiling, checkpointing |
| `tiles.py` | bbox subdivision | anything to do with progress |
| `checkpoint.py` | durable progress tracking | HTTP, fetching |
| `planet.py` | tiled + resumable fetch | writing, visualisation |
| `storage.py` | streaming object → file | query construction |
| `formats/base.py` | the writer contract | specific formats |
| `formats/geojson.py` | GeoJSON output | Parquet, folium |
| `formats/parquet.py` | Parquet output | GeoJSON, folium |
| `retry.py` | retry/backoff algorithm | knowing about Overpass |
| `cli.py` | CLI surface + spec parsing | query construction, writing |
| `map.py` | folium rendering | data filtering |
| `scripts/parquet_to_map_geojson.py` | pre-render filter + simplify | folium |

## Extension points

If you want to add a new behaviour, here is where it goes:

| Want to… | Add / change |
|---|---|
| Support a new OSM element type (e.g. include nodes again) | `_ALLOWED_TYPES` in `parser.py`, `_ELEMENT_TYPES` in `query.py`, `formats/geojson.py::_to_feature`. Update tests. |
| Support a new output format (e.g. FlatGeobuf, GeoPackage) | new `formats/<name>.py` implementing `FormatWriter`; register in `formats/__init__.open_writer`. |
| Support a different Overpass endpoint (self-hosted, Kumi, etc.) | `--endpoint` flag already exists. Defaults to public Overpass. |
| Persist checkpoints elsewhere (S3, Redis) | implement `CheckpointStore` Protocol; construct `Checkpoint(your_store)` in `planet.py`. |
| Add a CLI subcommand | add a `@cli.command(...)` in `cli.py`; add a `tests/test_cli_<name>.py`. |
| Add a new map style (clustering, choropleth) | swap `folium_map` in `map.py::render_map`. The GeoJSON input contract is stable. |
| Pre-filter the map differently | modify `scripts/parquet_to_map_geojson.py`. Don't try to bake this into `map.py`. |
| Support per-tile parallelism | `planet.py::fetch_planet` is currently sequential. Wrap in `concurrent.futures.ThreadPoolExecutor` and ensure `OverpassClient` is thread-safe (it owns its `httpx.Client`; consider one client per worker). |

## What is *not* in this codebase

Deliberately deferred or out of scope:

- **Alternative data sources** (Geofabrik planet files, BBBike, OSM-PBF).
  The Overpass API is the only source. If you need planet files, add a new
  source module that returns an `Iterable[OSMObject]` and plug it into
  `storage.write_objects`.
- **Per-tile concurrency / parallelism** beyond what Overpass serialises.
- **Per-tile schema evolution / migrations** of the Parquet file.
- **Authentication** to private Overpass instances beyond passing `--endpoint`
  with credentials in the URL.
- **Spatial filtering beyond bbox** (e.g. by country polygon).
- **Live updates / diffs** against the OSM minutely diffs.
- **A web UI**. The map is a static HTML file.
- **Local caching of Overpass responses.** If you need that, wrap
  `OverpassClient.fetch` with a cache decorator.
