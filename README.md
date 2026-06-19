# osm-tags-to-object

Download OpenStreetMap **ways + relations** (no nodes) that match a set of tags, stream the results to disk in GeoJSON or Parquet, and render an interactive map of polygons with their tags on hover.

Supports **resumable planet-wide fetches** via a tile grid + checkpoint file, and **streaming Parquet output** with bounded memory.

> **If you are a coding agent picking up this codebase, read [`AGENTS.md`](./AGENTS.md) first.** It is a condensed orientation with the module map, conventions, and gotchas. Deeper material lives under [`docs/`](./docs/).

## Table of contents

- [Quickstart](#quickstart)
- [Resumable planet fetch](#resumable-planet-fetch)
- [Data storage](#data-storage)
- [CLI](#cli)
- [Python API](#python-api)
- [Project layout](#project-layout)
- [How it works](#how-it-works)
- [Documentation](#documentation)

## Documentation

Detailed topical docs live under [`docs/`](./docs/):

- [`docs/architecture.md`](./docs/architecture.md) — end-to-end data flow, the data model, extension points.
- [`docs/operations.md`](./docs/operations.md) — runbook: dev setup, running tests, scaling a fetch, syncing to the HF bucket, debugging.
- [`docs/decisions.md`](./docs/decisions.md) — design rationale (why `out geom;`, why no nodes, why two-stage map, etc.).
- [`docs/gotchas.md`](./docs/gotchas.md) — known traps with reproduction notes.
- [`docs/milestones.md`](./docs/milestones.md) — project history: what was built when, and what was learned.

## Quickstart

```bash
# Fetch amenity=bench and amenity=fountain in Monaco, save as GeoJSON
uv run osm-tags-to-object fetch \
    --tags amenity=bench,fountain \
    --bbox 43.728,7.409,43.753,7.438 \
    -o ./data/monaco.geojson

# Render an interactive map of those polygons
uv run osm-tags-to-object map \
    -i ./data/monaco.geojson \
    -o ./data/monaco.html

# Push the data to the HF bucket
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object
```

Open `data/monaco.html` in a browser; hovering a polygon shows `key=value` pairs.

## Resumable planet fetch

```bash
# Start a planet-wide fetch, tiled 18 x 36 (= 648 tiles), checkpointed.
uv run osm-tags-to-object planet \
    --tags amenity=bench \
    --bbox -90,-180,90,180 \
    --tile-rows 18 --tile-cols 36 \
    --checkpoint ./data/planet-checkpoint.json \
    --format parquet \
    -o ./data/planet.parquet

# Got interrupted? Re-run the exact same command.
# Already-completed tiles are skipped; only the remaining ones are fetched.
uv run osm-tags-to-object planet ... --checkpoint ./data/planet-checkpoint.json ...
```

Tile keys are derived from the tile bbox, so the checkpoint file is portable across runs (as long as the bbox and tile dimensions match). A tile is marked done only after a successful response - including empty responses - so empty areas aren't re-queried on resume. A tile that fails partway is left unmarked and will be retried on resume.

**Output is also streamed.** `ParquetWriter` caps memory at one in-flight row group (default 10 000 rows). Memory usage stays bounded regardless of dataset size.

### Country-scale example: French forests

```bash
# Fetch all `landuse=forest` polygons across mainland France.
# 9 x 14 = 126 tiles of ~1 deg each, resumable via checkpoint.
uv run osm-tags-to-object planet \
    --tags landuse=forest \
    --bbox 42.3,-5.0,51.1,8.3 \
    --tile-rows 9 --tile-cols 14 \
    --checkpoint ./data/france-forest.cp.json \
    --format parquet \
    -o ./data/france-forest.parquet

# Build a map-friendly GeoJSON from the parquet
# (drops relations, keeps ways > 5 km^2 bbox, RDP-simplifies).
uv run python scripts/parquet_to_map_geojson.py \
    --input ./data/france-forest.parquet \
    --output ./data/france-forest.map.geojson \
    --min-bbox-km2 5

# Render the interactive map
uv run osm-tags-to-object map \
    -i ./data/france-forest.map.geojson \
    -o ./data/france-forest.html
```

The full France forest dataset is ~640 MB of Parquet with ~890 000 polygons (847 K ways + 42 K relations). The map-friendly GeoJSON drops to ~14 MB (~6 000 polygons: only ways whose bbox exceeds 5 km^2, simplified with Ramer-Douglas-Peucker). Hover any forest to see its OSM tags.

## Data storage

All output files go under `./data/`. That directory is gitignored and is the source for `hf sync`. See [Data storage](#data-storage) below for the sync commands.

## CLI

### `osm-tags-to-object fetch`

Single Overpass request, no tiling.

```text
osm-tags-to-object fetch [OPTIONS]

  Fetch OSM objects matching the given tags and stream them to a file.

Options:
  --tags TEXT          Comma-separated tag spec, e.g. 'amenity=bench,fountain,highway=bus_stop'.  [required]
  --bbox TEXT          Bounding box as south,west,north,east. Omit for planet-wide.
  --format [geojson|parquet]  Output format.  [default: geojson]
  -o, --output PATH    Output file path. Parent directories are created.  [required]
  --endpoint TEXT      Overpass API endpoint URL.
  --help               Show this message and exit.
```

### `osm-tags-to-object planet`

Tile a bbox and fetch tile-by-tile with checkpointing.

```text
osm-tags-to-object planet [OPTIONS]

  Fetch a large region tile-by-tile with checkpointing for resumability.

Options:
  --tags TEXT             Comma-separated tag spec.  [required]
  --bbox TEXT             Bounding box as south,west,north,east.  [required]
  --tile-rows INTEGER     Number of rows to split the bbox into.  [default: 4]
  --tile-cols INTEGER     Number of columns to split the bbox into.  [default: 4]
  --checkpoint PATH       Path to a checkpoint file. Re-running with the same path resumes.
  --format [geojson|parquet]  Output format.  [default: geojson]
  -o, --output PATH       Output file path.  [required]
  --endpoint TEXT         Overpass API endpoint URL.
  --help                  Show this message and exit.
```

### `osm-tags-to-object map`

```text
osm-tags-to-object map [OPTIONS]

  Render an interactive map of polygons from a GeoJSON file.

Options:
  -i, --input PATH   Input GeoJSON file produced by 'fetch' or 'planet'.  [required]
  -o, --output PATH  Output HTML file.  [required]
  --help             Show this message and exit.
```

### Tag spec syntax

| Spec | Result |
|---|---|
| `amenity=bench` | `{"amenity": "bench"}` |
| `amenity=bench,fountain` | `{"amenity": ["bench", "fountain"]}` |
| `amenity=bench,highway=bus_stop` | `{"amenity": "bench", "highway": "bus_stop"}` |
| `amenity=bench,fountain,highway=bus_stop` | `{"amenity": ["bench", "fountain"], "highway": "bus_stop"}` |

## Python API

```python
from osm_tags_to_object import (
    OverpassClient,
    TagFilter,
    fetch_matching_objects,
    write_objects,
)

client = OverpassClient()  # uses the public Overpass instance with retry/backoff
objects = fetch_matching_objects(
    TagFilter({"amenity": ["bench", "fountain"]}),
    bbox=(43.728, 7.409, 43.753, 7.438),
    client=client,
)

write_objects(objects, "./data/monaco.geojson", format="geojson")
```

Resumable planet fetch:

```python
from osm_tags_to_object import (
    Checkpoint, FileCheckpointStore, OverpassClient, fetch_planet, write_objects,
)

cp = Checkpoint(FileCheckpointStore("./data/planet-checkpoint.json"))
with OverpassClient() as client:
    objects = fetch_planet(
        {"amenity": "bench"},
        bbox=(-90.0, -180.0, 90.0, 180.0),
        checkpoint=cp,
        tile_rows=18,
        tile_cols=36,
        client=client,
    )
    write_objects(objects, "./data/planet.parquet", format="parquet")
```

All components are independently usable. `OverpassClient` accepts an injected `httpx.Client` for tests, a custom `RetryConfig`, and a `sleep` function for backoff injection.

## Project layout

```
src/osm_tags_to_object/
    tags.py        # TagFilter dataclass (key -> value | list[value])
    query.py      # Overpass QL builder: only `way` + `relation`, never `node`
    client.py     # OverpassClient (httpx + retry + descriptive User-Agent)
    parser.py     # Overpass JSON -> list[OSMObject]; drops node elements
    models.py     # OSMObject dataclass (type, id, tags, geometry, members)
    pipeline.py   # fetch_matching_objects: query -> fetch -> parse
    tiles.py      # TileGrid: split a bbox into a regular grid of Tiles
    checkpoint.py # Checkpoint + FileCheckpointStore (atomic JSON write)
    planet.py     # fetch_planet: tiled + checkpointed iteration
    storage.py    # write_objects: streams an iterable of objects to disk
    formats/
        base.py        # FormatWriter protocol (context manager + write())
        geojson.py     # Streaming GeoJSON FeatureCollection writer
        parquet.py     # Streaming Parquet writer (pyarrow; row-group flush)
    retry.py      # Exponential-backoff retry helper (Retry-After aware)
    cli.py        # Click CLI (fetch, planet, map) + spec parsers
    map.py        # Folium interactive map (polygons + hover tooltips)

tests/
    test_tags.py, test_query.py, test_parser.py, test_client.py,
    test_pipeline.py, test_retry.py, test_storage.py,
    test_formats_geojson.py, test_formats_parquet.py, test_formats_parquet_streaming.py,
    test_cli_tags_spec.py, test_cli.py, test_cli_planet.py, test_map.py,
    test_checkpoint.py, test_tiles.py, test_planet.py
```

## How it works

1. **`TagFilter`** holds `{key: value | list[value]}`. Multiple values for the same key become OR-ed selectors.
2. **`query.py`** turns a filter (+ optional `bbox`) into an Overpass QL query that selects only `way` and `relation` elements, with `out geom;` so each way's coordinates are returned inline (no second pass for nodes).
3. **`OverpassClient`** wraps a single POST in `retry_with_backoff`. The public Overpass instance returns 406 to a `python-httpx` User-Agent and aggressively rate-limits with 429s; the client sets `Accept: application/json`, a descriptive `User-Agent`, and respects `Retry-After`.
4. **`parser.py`** drops every `node` element and builds `OSMObject` instances. Ways get a `geometry` tuple of `(lat, lon)` pairs. Relations keep their raw `members` (which may carry their own `geometry`).
5. **`storage.write_objects`** streams an `Iterable[OSMObject]` straight to a `GeoJSONWriter` or `ParquetWriter`. `ParquetWriter` flushes a row group every `row_group_size` rows (default 10 000), bounding peak memory regardless of how many objects are written.
6. **`planet.fetch_planet`** splits a bbox into a `rows x cols` grid (via `TileGrid`), skips tiles already in the `Checkpoint`, and only marks a tile done after its full response has been consumed. Resumable across process restarts.
7. **`map.render_map`** reads a GeoJSON FeatureCollection and builds a self-contained Leaflet HTML file; each polygon's tags appear as a tooltip on hover and as a popup on click.

## Data storage

All data for this project lives on the Hugging Face bucket:

```
hf://buckets/NoeFlandre/osm-tags-to-object
```

**Do not store data locally.** Anything that would otherwise live in `./data/` (or anywhere else on disk) must be synced to and from the bucket using the `hf` CLI.

### Pulling data from the bucket

```bash
hf sync hf://buckets/NoeFlandre/osm-tags-to-object ./data
```

### Pushing local changes to the bucket

```bash
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object
```

### Typical workflow

1. Pull the latest data: `hf sync hf://buckets/NoeFlandre/osm-tags-to-object ./data`
2. Run a `fetch` or `planet` (writes to `./data/...`).
3. Push your changes back: `hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object`

The `./data/` directory is gitignored, so it stays in sync with the bucket rather than the repository.
