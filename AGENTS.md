# AGENTS.md

> Read this first if you are a coding agent picking up this codebase. It is a
> condensed orientation; deeper material is in `docs/`.

## What this project does

Download OpenStreetMap **ways + relations** (deliberately not nodes) that
match a set of tags, stream them to disk in **GeoJSON** or **Parquet**, and
optionally render an interactive **Leaflet** map with hover tooltips.

It is meant to scale: a country-wide fetch of `landuse=forest` across France
has been demonstrated end-to-end (890 000 polygons, ~640 MB Parquet).

Data lives **only on a Hugging Face bucket** (`hf://buckets/NoeFlandre/osm-tags-to-object`),
never on disk long-term. The `./data/` directory is gitignored and exists
only as the staging area for `hf sync`.

## How to run the test suite

```bash
uv run pytest                  # 92 tests, ~1 s on a warm cache
uv run pytest tests/test_X.py  # one module
```

Tests use `httpx.MockTransport` to avoid hitting the network. They inject
`OverpassClient(retry_config=RetryConfig(max_attempts=1), sleep=lambda _: None)`
so retry/backoff is a no-op during the test.

## How to run a fetch

```bash
# Small area, one query, geojson output
uv run osm-tags-to-object fetch \
    --tags amenity=bench,fountain \
    --bbox 43.728,7.409,43.753,7.438 \
    -o ./data/example.geojson

# Country / continent, tiled + checkpointed
uv run osm-tags-to-object planet \
    --tags landuse=forest \
    --bbox 42.3,-5.0,51.1,8.3 \
    --tile-rows 9 --tile-cols 14 \
    --checkpoint ./data/example.cp.json \
    --format parquet \
    -o ./data/example.parquet
```

`./data/` is gitignored. After a fetch, push with:

```bash
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object
rm data/*  # don't keep data locally
```

## How to make a map

```bash
# 1. If you only have parquet (large datasets):
uv run python scripts/parquet_to_map_geojson.py \
    --input ./data/example.parquet \
    --output ./data/example.map.geojson \
    --min-bbox-km2 5

# 2. Render the map
uv run osm-tags-to-object map \
    -i ./data/example.map.geojson \
    -o ./data/example.html
```

Open `data/example.html` in a browser; hover any polygon to see its tags.

## Module map

Read top-down: data flows from query → fetch → parse → write → map.

| Module | Role |
|---|---|
| `tags.py` | `TagFilter` dataclass. |
| `query.py` | Builds Overpass QL. Always `out geom;`; never selects nodes. |
| `client.py` | `OverpassClient`: `httpx` POST wrapped in `retry_with_backoff`. Sends a descriptive `User-Agent` and `Accept: application/json` per request. |
| `parser.py` | Overpass JSON → `list[OSMObject]`. Drops every node. |
| `models.py` | `OSMObject` frozen dataclass. |
| `pipeline.py` | `fetch_matching_objects(filter, bbox, client)` — single query, in-memory list. |
| `tiles.py` | `TileGrid`: deterministic bbox subdivision, stable keys. |
| `checkpoint.py` | `Checkpoint` + `FileCheckpointStore`. Atomic writes (`.tmp` + rename). |
| `planet.py` | `fetch_planet(tags, bbox, checkpoint, ...)` — yields objects tile-by-tile, marks tiles done on success. |
| `storage.py` | `write_objects(iter, path, format)` — streams into a `FormatWriter`. |
| `formats/base.py` | `FormatWriter` Protocol (ctx mgr + `write(obj)`). |
| `formats/geojson.py` | Streaming GeoJSON FeatureCollection writer. |
| `formats/parquet.py` | `ParquetWriter` using `pyarrow.ParquetWriter`. Buffers up to `row_group_size` (default 10 000) rows. |
| `retry.py` | `retry_with_backoff(op, config, sleep)`. Exponential backoff, `Retry-After`-aware. |
| `cli.py` | Click group: `fetch`, `planet`, `map`. Spec parsers live here too. |
| `map.py` | Folium HTML map. One `folium.GeoJson` per feature with tooltip + popup. |
| `scripts/parquet_to_map_geojson.py` | Standalone script: parquet → folium-friendly GeoJSON (drops relations, filters by bbox area, RDP-simplifies). |

## Conventions

- **TDD**: production code only after a failing test that has been watched
  fail. New feature? Write the test first.
- **Type hints + dataclasses**: prefer them over classes with `__init__`.
- **No mocks unless unavoidable**: use real implementations and inject only
  the seams (HTTP transport, sleep clock, retry config).
- **Streaming by default**: every collection returned from a public
  function is an iterator, not a list, unless there's a strong reason.
- **Coordinate order**: `OSMObject.geometry` is `(lat, lon)` tuples. GeoJSON
  `coordinates` is `[lon, lat]`. Folium takes `(lat, lon)` for `Polygon(location=…)`.
  All conversions are explicit and tested.
- **No data on disk**: anything written under `./data/` is meant to leave
  the machine via `hf sync`.

## Critical gotchas (full list in `docs/gotchas.md`)

1. **Overpass returns HTTP 406** to the default `python-httpx/0.28.1`
   `User-Agent`. Set a descriptive one (already done in `OverpassClient`).
2. **Overpass also returns 406** for `Accept: */*`. We send
   `Accept: application/json` per request.
3. **The public Overpass cannot serve planet-wide single queries** in
   reasonable time. Use `planet` (tiled) for any region > ~1° × 1°.
4. **Folium chokes above ~10 K features** in a single HTML. Pre-filter
   with `scripts/parquet_to_map_geojson.py` before rendering.
5. **Parquet schema is part of the contract** — adding/removing columns
   breaks downstream readers. If you change `_SCHEMA` in
   `formats/parquet.py`, also update `scripts/parquet_to_map_geojson.py`.

## Where to look next

- `docs/architecture.md` — end-to-end data flow, data model, extension points.
- `docs/operations.md` — runbook: dev setup, scaling, resuming, syncing.
- `docs/decisions.md` — *why* the code is the way it is.
- `docs/gotchas.md` — full list of traps with reproduction notes.
- `docs/milestones.md` — what was built when, and what was learned.

## Style for new code

- One responsibility per module.
- Public functions get docstrings; private helpers don't have to.
- Tests live in `tests/test_<module>.py`, mirroring the module name.
- When adding a CLI command, write a `CliRunner`-based integration test
  in `tests/test_cli.py` or `tests/test_cli_<command>.py`.
- When adding a CLI flag, update both the `--help` output (auto) and
  the `README.md` CLI reference table.
