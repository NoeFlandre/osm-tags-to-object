# Operations

Runbook for day-to-day work on this project: setup, running, scaling, syncing, debugging.

## Local development setup

Requirements:

- Python 3.12 (declared in `pyproject.toml`).
- [`uv`](https://docs.astral.sh/uv/) for dependency management.
- [`hf`](https://huggingface.co/docs/huggingface_hub) CLI for the data bucket.
- `git` for version control.

Clone and install:

```bash
git clone https://github.com/NoeFlandre/osm-tags-to-object
cd osm-tags-to-object
uv sync               # create .venv and install deps
uv run pytest         # 92 tests should pass
uv run osm-tags-to-object --help
```

`uv sync` creates `.venv/` (gitignored). All `uv run …` commands use it
implicitly.

## Running the test suite

```bash
uv run pytest                          # all tests
uv run pytest tests/test_retry.py -v   # one module
uv run pytest -k parquet               # by keyword
uv run pytest --tb=long                # show full tracebacks on failure
```

Tests use `httpx.MockTransport` so no network is touched. Retry config is
injected with `max_attempts=1` and `sleep=lambda _: None` so backoff is a
no-op.

When writing a new test, follow TDD:

1. Write the test. Run it. Watch it fail.
2. Implement the minimum to pass. Run it. Watch it pass.
3. Refactor while keeping it green.
4. Commit.

See [`AGENTS.md`](../AGENTS.md) for the conventions.

## Single-area fetch

For a small bbox (~a city or smaller), use `fetch`:

```bash
uv run osm-tags-to-object fetch \
    --tags amenity=bench,fountain \
    --bbox 43.728,7.409,43.753,7.438 \
    --format geojson \
    -o ./data/monaco.geojson
```

- One HTTP request. No checkpointing. If it fails, run it again.
- GeoJSON output is human-readable but ~4× larger than Parquet for the
  same data.
- Suitable for: debug runs, one-off queries, anything under ~10 MB.

## Country / continent fetch

For anything bigger than a small region, use `planet` with tiling and
checkpointing:

```bash
uv run osm-tags-to-object planet \
    --tags landuse=forest \
    --bbox 42.3,-5.0,51.1,8.3 \
    --tile-rows 9 --tile-cols 14 \
    --checkpoint ./data/example.cp.json \
    --format parquet \
    -o ./data/example.parquet
```

- The bbox is split into `tile-rows × tile-cols` equal tiles.
- Each tile is one HTTP request; success marks the tile done.
- Re-running with the same `--checkpoint` resumes from where you left off.
- `--format parquet` is strongly recommended above ~100 MB; GeoJSON at this
  scale gets unwieldy.

### Choosing tile dimensions

Trade-offs:

| Smaller tiles | Larger tiles |
|---|---|
| More HTTP requests | Fewer HTTP requests |
| Each response fits comfortably in memory | Each response can be very large |
| More chances to hit Overpass rate limits | Fewer chances to hit limits |
| Smaller per-tile responses can be served faster | A single tile can time out |

Rule of thumb: aim for 50–500 tiles per run. Adjust if you see:

- **`504 Gateway Timeout`**: tiles too large; increase `tile-rows`/`tile-cols`.
- **Many `429 Too Many Requests`**: too many tiles; decrease.

### Resuming after an interruption

Just re-run the exact same command. Already-done tiles (in the checkpoint
file) are skipped. A tile is *only* marked done after a successful response,
so an interrupted run picks up exactly where it left off.

```bash
$ # Process started, ran for 20 minutes, hit Ctrl-C
$ # Re-run:
$ uv run osm-tags-to-object planet ... --checkpoint ./data/example.cp.json
Resuming from checkpoint data/example.cp.json: 73/126 tiles done
Done: 126/126 tiles done; wrote data/example.parquet
```

### What if a tile persistently fails?

The exception bubbles up and the run stops. The failing tile stays
unmarked in the checkpoint, so re-running retries it. If a tile is
genuinely broken (e.g. Overpass timeout on a specific bbox), you can
manually mark it done in the checkpoint file or skip it by reducing
the tile grid and adjusting the bbox.

## Making a map

Two-step:

```bash
# 1. Filter parquet → folium-friendly GeoJSON.
#    Drops relations, keeps ways > --min-bbox-km2, RDP-simplifies.
uv run python scripts/parquet_to_map_geojson.py \
    --input ./data/example.parquet \
    --output ./data/example.map.geojson \
    --min-bbox-km2 5

# 2. Render the HTML map.
uv run osm-tags-to-object map \
    -i ./data/example.map.geojson \
    -o ./data/example.html
```

Open `data/example.html` in a browser.

### Tuning the map size

The bottleneck is browser load time, not render time. Folium inlines the
GeoJSON into the HTML, so the file size roughly equals
`GeoJSON size + Leaflet boilerplate`. Practical limits:

| GeoJSON features | HTML file size | Load time |
|---|---|---|
| ~1 000 | ~3 MB | fast |
| ~6 000 | ~25 MB | acceptable |
| ~30 000 | ~120 MB | slow but works |
| ~100 000+ | ~500 MB+ | unusable |

Tune with:

- `--min-bbox-km2 N`: drop polygons whose bbox is below N km². Larger N → fewer features.
- `--rdp-epsilon-deg D`: simplification tolerance. Larger D → fewer vertices per polygon.

There are two failure modes to watch for:

1. **Polygon dropped by simplification.** If `D` is too large RDP may
   reduce a polygon to <3 vertices and the writer skips it. The script
   reports `Below size threshold` for these.
2. **Polygon collapsed to a line.** `D` close to the polygon's diameter
   can yield a degenerate ring. The `len(simplified) < 3` check in the
   script catches this.

## Hugging Face bucket workflow

Bucket: `hf://buckets/NoeFlandre/osm-tags-to-object`.

```bash
# Pull (e.g. on a fresh machine)
hf sync hf://buckets/NoeFlandre/osm-tags-to-object ./data

# … work locally …

# Push
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object

# Clean up locally so the data only lives on the bucket
rm data/*
```

`hf sync` is idempotent: it computes a plan based on mtimes and sizes
before transferring anything. To preview without transferring:

```bash
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object --dry-run
```

To inspect bucket contents:

```bash
hf buckets ls hf://buckets/NoeFlandre/osm-tags-to-object
```

To delete specific files from the bucket:

```bash
hf buckets rm hf://buckets/NoeFlandre/osm-tags-to-object/france-forest.geojson
```

## End-to-end workflow for a new tag

A typical "I want all the X in France" task:

1. Pick a tag and bbox.
2. `uv run osm-tags-to-object fetch` against a *small* bbox to verify
   the tag is mapped and the response is reasonable.
3. `uv run osm-tags-to-object planet` against the full bbox, tiled
   appropriately, with checkpointing.
4. `scripts/parquet_to_map_geojson.py` to filter.
5. `osm-tags-to-object map` to render.
6. `hf sync` to push; `rm data/*` to clean up.

## Debugging

### Tests fail with `ModuleNotFoundError: No module named 'osm_tags_to_object'`

`pytest.ini_options.pythonpath = ["src"]` in `pyproject.toml` handles this
when you run `uv run pytest`. If you `python -m pytest` outside `uv`, the
import will fail. Either set `PYTHONPATH=src` or always use `uv run`.

### Tests fail with `ModuleNotFoundError: No module named 'pyarrow'`

You ran outside `uv`. Use `uv run pytest`.

### Live fetch returns HTTP 406

You (or a new endpoint) forgot the headers. The `OverpassClient` sets both
`Accept: application/json` and a descriptive `User-Agent`; verify by
running:

```python
from osm_tags_to_object import OverpassClient
import httpx

captured = {}
def handler(req):
    captured["ua"] = req.headers.get("user-agent")
    captured["accept"] = req.headers.get("accept")
    return httpx.Response(200, json={"elements": []})

client = OverpassClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
client.fetch("out;")
client.close()
assert captured["ua"] and "python-httpx" not in captured["ua"]
assert captured["accept"] == "application/json"
```

### Live fetch is rate-limited (429)

Increase backoff. The default `RetryConfig` is `max_attempts=5,
base_delay=1.0, max_delay=60.0, backoff_factor=2.0`. For long runs
against the public Overpass, try:

```python
from osm_tags_to_object import OverpassClient, RetryConfig
client = OverpassClient(
    retry_config=RetryConfig(
        max_attempts=8,
        base_delay=5.0,
        max_delay=120.0,
        backoff_factor=2.0,
    ),
)
```

`Retry-After` headers are respected automatically.

### The map HTML is enormous (>100 MB)

Pre-filter more aggressively. Either raise `--min-bbox-km2` or coarsen
the source parquet by re-running the fetch with a different tag spec
that excludes small features.

### A parquet file won't open in another tool

The schema is documented in [`docs/architecture.md`](./architecture.md#parquet-schema).
Some tools want a flat row instead of nested structs; in DuckDB:

```sql
SELECT type, id, tags, unnest(geometry) AS point
FROM read_parquet('france-forest.parquet');
```

### Re-running a fetch doesn't resume

- Different `--bbox` or `--tile-rows`/`--tile-cols` → different tile
  keys → nothing matches the checkpoint.
- Checkpoint file deleted or moved.

The tile keys are deterministic *given the same bbox and grid*, so as
long as those three values match, resume works.
