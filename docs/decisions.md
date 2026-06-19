# Design decisions

The *why* behind the code. Each entry states the decision, what it traded off against, and what we lose by changing it.

## 1. Only ways and relations, never nodes

**Decision.** `query.py` never emits `node[...]` selectors. `parser.py` drops every element whose `type == "node"`.

**Why.** Stated requirement of the project ("Open Street Maps objects ... except the nodes"). Independent motivation: nodes are 1–2 orders of magnitude more numerous than ways/relations and would dominate response size without contributing to the polygon map.

**Cost.** If you ever need per-node attributes (e.g. address points), this codebase can't help.

## 2. `out geom;` instead of `out body; >; out skel qt;`

**Decision.** The Overpass QL emitted by `build_overpass_query` ends with `out geom;`.

**Why.** `out geom` returns each way's node coordinates inline, eliminating a second pass that would fetch every referenced node. One HTTP round-trip per tile instead of (potentially) several, and a smaller response for sparse geometries.

**Alternatives considered.**

- `out body; >; out skel qt;`: returns ways/relations with tags *and* their referenced nodes as separate elements. Cleaner separation but doubles response size for ways.
- `out center;`: returns just the centroid. Cheap but useless for drawing polygons.

**Cost.** We lose node IDs as integers (only lat/lon pairs survive). If a downstream consumer wants IDs, the code needs an option to switch.

## 3. Public Overpass as the default endpoint

**Decision.** `OverpassClient.DEFAULT_URL = "https://overpass-api.de/api/interpreter"`.

**Why.** Zero setup, no auth, well-known. Fine for prototyping and small runs.

**Cost.** Aggressively rate-limited, blocks Python User-Agents, and can't serve planet-wide queries. For serious work, point `--endpoint` at a self-hosted Overpass or an alternative (Kumi, Maps.mail.ru, etc.).

## 4. Descriptive `User-Agent` and explicit `Accept` header

**Decision.** `OverpassClient.fetch` sends `User-Agent: osm-tags-to-object/0.1 (https://github.com/...)` and `Accept: application/json` on every request.

**Why.** Discovered empirically: the public Overpass returns HTTP 406 to `python-httpx/0.28.1` (it pattern-matches common library strings) and to `Accept: */*`. Both must be set.

**Cost.** A small amount of boilerplate on every request. Acceptable.

## 5. Retry as a generic helper, not HTTP-coupled

**Decision.** `retry.py::retry_with_backoff(op, config, sleep)` is generic. It catches `httpx.HTTPStatusError` and a configurable list of network exceptions.

**Why.** Decouples retry policy from the Overpass client. Tests can call `retry_with_backoff` directly with a fake op, and `OverpassClient` injects its own `RetryConfig` and `sleep` function.

**Cost.** Slightly more abstraction than a decorator would provide. We considered a `@retry` decorator; the function form is more testable and easier to swap.

## 6. Streaming Parquet via `pyarrow.parquet.ParquetWriter`

**Decision.** `formats/parquet.py` uses `ParquetWriter` and flushes a row group every `row_group_size` rows (default 10 000).

**Why.** A naive `pa.Table.from_pylist(all_rows).write_to(...)` buffers the whole dataset in memory. For a 900 K-row dataset that's ~2 GB of Python objects before pyarrow ever sees them. `ParquetWriter` keeps memory bounded by `row_group_size × row_width`, which is ~30 MB regardless of dataset size.

**Alternatives considered.**

- `pq.write_table(table, path)`: simple, but requires building the whole `Table` first.
- Custom chunking + multiple files: more moving parts, no advantage.

**Cost.** The file is written progressively, so a crash before `close()` can leave a malformed file. The checkpoint layer above partially mitigates this — a crashed `planet` run can be resumed and the partial parquet deleted. We do not currently detect or repair partially-written parquet.

## 7. Tiling + checkpoint for scale

**Decision.** Above ~1° × 1° we tile the bbox into a regular grid and write a per-tile progress file.

**Why.** The public Overpass times out on large single queries. Even when it doesn't, a single query that fails loses all progress. Tiling gives bounded per-query cost and per-tile resumability.

**Cost.** The user has to pick a tile count. There's no auto-sizing. We give rough guidance in [`operations.md`](./operations.md#choosing-tile-dimensions) but it's still a manual knob.

## 8. Atomic JSON writes for the checkpoint

**Decision.** `FileCheckpointStore.save` writes to `<path>.tmp` then `Path.replace`s it onto `<path>`.

**Why.** A crash mid-write would leave a half-written JSON file. On startup, half-written JSON parses to garbage; treating that as "empty" is the same as starting fresh. An atomic rename means either the old checkpoint or the new one is visible, never a mix.

**Cost.** One extra filesystem rename per tile. Negligible.

## 9. Two-stage map: filter parquet → render GeoJSON

**Decision.** The interactive map is built in two steps. `scripts/parquet_to_map_geojson.py` produces a small GeoJSON; `osm-tags-to-object map` renders it.

**Why.** Folium inlines the GeoJSON into the HTML, so file size is roughly 1:1 plus Leaflet boilerplate. 890 K polygons → ~3 GB HTML. Beyond ~50 K polygons, browsers choke on load time.

Splitting the filter from the renderer means:
- The filter can be re-tuned (smaller threshold, different simplification) without re-fetching.
- The map can be re-rendered with a different library (kepler.gl, Mapbox GL) without touching the data pipeline.
- Tests can target either side independently.

**Alternatives considered.**

- Streaming folium: folium doesn't have a streaming mode; GeoJson layers are loaded eagerly.
- Vector tiles (Mapbox Vector Tile / PMTiles): heavier stack, but the right answer at true country scale. Deferred.

## 10. Bbox-area filter, not polygon area

**Decision.** `scripts/parquet_to_map_geojson.py` filters by polygon bbox area, not the polygon area itself.

**Why.** Bbox area is O(N) over vertices with no planar projection. Polygon area needs either a proper projection (heavy) or a spherical excess formula (acceptable but slower). At country zoom the threshold is conservative enough that the difference doesn't matter.

**Cost.** Real area is always ≤ bbox area, so the cut is slightly aggressive — small polygons that happen to have large bboxes get kept. For the visualisation use case, this is what you want.

## 11. Ramer-Douglas-Peucker simplification at ~50 m

**Decision.** Default `--rdp-epsilon-deg=0.0005` ≈ 50 m at France's latitude.

**Why.** A typical OSM forest has 100–1000 vertices. At country zoom you need 5–20. RDP preserves shape while collapsing collinear runs. 50 m is below pixel size at zoom level 6, so the simplification is invisible.

**Cost.** Re-introducing full detail (e.g. for a zoomed-in view) requires keeping the un-simplified parquet around. We do, via `data/*.parquet`.

## 12. Folium, not a more "modern" map library

**Decision.** `map.py` uses `folium` to render the HTML.

**Why.** Folium is the smallest possible dependency for "give it a GeoJSON, get a self-contained HTML file". No tile server, no API key, no JS bundler.

**Cost.** Folium embeds Leaflet 1.x and an older jQuery; modern maps look nicer. Performance caps out around 30 K polygons in a single layer. For larger visualisations, replace `render_map` (see [`architecture.md` extension points](./architecture.md#extension-points)).

## 13. `Click` for the CLI

**Decision.** `cli.py` uses `click`.

**Why.** Smallest CLI dep that gives `--help` autodocs, nested commands, and `CliRunner`-based tests. argparse would also work but lacks the testing utilities.

**Cost.** One more runtime dependency.

## 14. `uv` for project management

**Decision.** Project is set up with `uv`. `pyproject.toml` declares the project; `uv.lock` is committed; the install command is `uv sync`.

**Why.** Fast, deterministic, single binary. Replaces pip + venv + pip-tools.

**Cost.** Requires `uv` to be installed. Anyone with `pip` can still read `pyproject.toml` and `uv.lock` to install by hand.

## 15. Data only on the Hugging Face bucket

**Decision.** `./data/` is gitignored. After every fetch, the user is expected to `hf sync` and then `rm data/*`.

**Why.** GeoJSON and Parquet for country-scale fetches are hundreds of MB to GB. They do not belong in the repository.

**Cost.** Every machine working on the project must do its own `hf sync` to get the data. Acceptable: it's a single command.

## 16. TDD throughout, including for "obvious" features

**Decision.** Every public function has a test that was watched fail before the implementation was written. Even things like `parse_tags_spec("amenity=bench")` got a dedicated test.

**Why.** "Tests written after code pass immediately, proving nothing." TDD forces the test to assert the *requirement*, not the *implementation*, and surfaces edge cases early.

**Cost.** Slower start. Pays off the first time we touch the code again.

## Things we considered and explicitly rejected

- **Including nodes.** See decision 1.
- **Async I/O.** No measured benefit at our scale (≤ ~600 HTTP requests per run). Adds complexity (`asyncio` + `httpx.AsyncClient`). Revisit if we ever parallelise across many endpoints.
- **Caching Overpass responses.** Would let us resume without network access. Not needed: tile-level checkpointing already does the job.
- **A relational store (PostGIS, DuckDB file) for the data.** Parquet is already columnar and analytics-friendly. A DB would add a runtime dep for no gain at this scale.
- **A web service.** Static HTML map is good enough for the prototype use case.
- **Schema migrations on the parquet file.** We have one consumer (`scripts/parquet_to_map_geojson.py`). When a second consumer appears, we'll introduce a `version` column.
