# osm-tags-to-object

Download OpenStreetMap **ways + relations** (no nodes) that match a set of tags, stream the results to disk in GeoJSON or Parquet, and render an interactive map of polygons with their tags on hover.

## Table of contents

- [Quickstart](#quickstart)
- [Data storage](#data-storage)
- [CLI](#cli)
- [Python API](#python-api)
- [Project layout](#project-layout)
- [How it works](#how-it-works)

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

## Data storage

All output files go under `./data/`. That directory is gitignored and is the source for `hf sync`. See [Data storage](#data-storage) below for the sync commands.

## CLI

### `osm-tags-to-object fetch`

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

Tag spec syntax:

| Spec | Result |
|---|---|
| `amenity=bench` | `{"amenity": "bench"}` |
| `amenity=bench,fountain` | `{"amenity": ["bench", "fountain"]}` |
| `amenity=bench,highway=bus_stop` | `{"amenity": "bench", "highway": "bus_stop"}` |
| `amenity=bench,fountain,highway=bus_stop` | `{"amenity": ["bench", "fountain"], "highway": "bus_stop"}` |

### `osm-tags-to-object map`

```text
osm-tags-to-object map [OPTIONS]

  Render an interactive map of polygons from a GeoJSON file.

Options:
  -i, --input PATH   Input GeoJSON file produced by 'fetch'.  [required]
  -o, --output PATH  Output HTML file.  [required]
  --help             Show this message and exit.
```

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
    storage.py    # write_objects: streams an iterable of objects to disk
    formats/
        base.py        # FormatWriter protocol (context manager + write())
        geojson.py     # Streaming GeoJSON FeatureCollection writer
        parquet.py     # Parquet writer (pyarrow)
    retry.py      # Exponential-backoff retry helper (Retry-After aware)
    cli.py        # Click CLI (fetch, map) + spec parsers
    map.py        # Folium interactive map (polygons + hover tooltips)

tests/
    test_tags.py, test_query.py, test_parser.py, test_client.py,
    test_pipeline.py, test_retry.py, test_storage.py,
    test_formats_geojson.py, test_formats_parquet.py,
    test_cli_tags_spec.py, test_cli.py, test_map.py
```

## How it works

1. **`TagFilter`** holds `{key: value | list[value]}`. Multiple values for the same key become OR-ed selectors.
2. **`query.py`** turns a filter (+ optional `bbox`) into an Overpass QL query that selects only `way` and `relation` elements, with `out geom;` so each way's coordinates are returned inline (no second pass for nodes).
3. **`OverpassClient`** wraps a single POST in `retry_with_backoff`. The public Overpass instance returns 406 to a `python-httpx` User-Agent and aggressively rate-limits with 429s; the client sets `Accept: application/json`, a descriptive `User-Agent`, and respects `Retry-After`.
4. **`parser.py`** drops every `node` element and builds `OSMObject` instances. Ways get a `geometry` tuple of `(lat, lon)` pairs. Relations keep their raw `members` (which may carry their own `geometry`).
5. **`storage.write_objects`** streams an `Iterable[OSMObject]` straight to a `GeoJSONWriter` or `ParquetWriter`, so we never hold the full result set in memory.
6. **`map.render_map`** reads a GeoJSON FeatureCollection and builds a self-contained Leaflet HTML file; each polygon's tags appear as a tooltip on hover and as a popup on click.

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
2. Run a `fetch` (writes to `./data/...`).
3. Push your changes back: `hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object`

The `./data/` directory is gitignored, so it stays in sync with the bucket rather than the repository.
