# Gotchas

Things that surprised us. Each entry has a reproduction.

## 1. The public Overpass returns HTTP 406 to `python-httpx/...`

**Symptom.** First call to `OverpassClient.fetch` returns `HTTPStatusError: Client error '406 Not Acceptable' for url 'https://overpass-api.de/api/interpreter'`.

**Cause.** The Overpass server pattern-matches common library User-Agents and rejects them with 406.

**Reproduction.**

```bash
curl -sS -X POST -H "Accept: application/json" \
    --data-urlencode 'data=[out:json][timeout:10];out;' \
    https://overpass-api.de/api/interpreter -w "\n%{http_code}\n" --max-time 30
# HTTP 200 with a curl UA
curl -sS -X POST -H "Accept: application/json" \
    -H "User-Agent: python-httpx/0.28.1" \
    --data-urlencode 'data=[out:json][timeout:10];out;' \
    https://overpass-api.de/api/interpreter -w "\n%{http_code}\n" --max-time 30
# HTTP 406 with the python-httpx UA
```

**Fix.** `OverpassClient` already sends a descriptive User-Agent per request (`osm-tags-to-object/0.1 (https://github.com/...)`). If you bypass it (e.g. with a custom `httpx.Client`), set the UA yourself.

Tests covering this: `test_client_sets_a_descriptive_user_agent`.

## 2. The public Overpass also returns 406 to `Accept: */*`

**Symptom.** Same 406 even when the User-Agent is fine.

**Cause.** Overpass returns 406 if the request's `Accept` doesn't match what the server is willing to send.

**Reproduction.**

```bash
curl -sS -X POST -H "Accept: */*" \
    --data-urlencode 'data=[out:json][timeout:10];out;' \
    https://overpass-api.de/api/interpreter -w "\n%{http_code}\n" --max-time 30
# HTTP 406
curl -sS -X POST -H "Accept: application/json" \
    --data-urlencode 'data=[out:json][timeout:10];out;' \
    https://overpass-api.de/api/interpreter -w "\n%{http_code}\n" --max-time 30
# HTTP 200
```

**Fix.** `OverpassClient` sends `Accept: application/json` on every request.

Tests covering this: `test_client_sets_accept_header_to_json`.

## 3. `retry_config` injected into `OverpassClient` defaults still take effect

**Symptom.** A test that wants instant failure on 429 takes ~30 s because the default `RetryConfig` retries with backoff.

**Cause.** `RetryConfig(max_attempts=5, base_delay=1.0, backoff_factor=2.0)` is the *default*, so unless you pass `retry_config=RetryConfig(max_attempts=1)`, the test waits through the backoff ladder.

**Fix.** Pass an explicit `RetryConfig(max_attempts=N)` and `sleep=lambda _: None` in tests:

```python
client = OverpassClient(
    http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    retry_config=RetryConfig(max_attempts=1),
    sleep=lambda _: None,
)
```

## 4. Public Overpass cannot serve planet-wide single queries

**Symptom.** A query against `(-90, -180, 90, 180)` either times out or returns `429` after partial results.

**Cause.** The public Overpass instance enforces a maximum bbox size per query. It's roughly the size of a small country.

**Fix.** Use the `planet` subcommand with tiling:

```bash
uv run osm-tags-to-object planet \
    --tags amenity=bench \
    --bbox -90,-180,90,180 \
    --tile-rows 18 --tile-cols 36 \
    --checkpoint ./data/planet.cp.json \
    -o ./data/planet.parquet
```

## 5. Folium inlines GeoJSON into HTML

**Symptom.** `france-forest.html` is hundreds of MB; the browser hangs on load.

**Cause.** `folium.Map.save()` writes a self-contained HTML with the GeoJSON embedded as JavaScript.

**Mitigation.** Pre-filter with `scripts/parquet_to_map_geojson.py` before rendering. Aim for `<30 K` features and `<120 MB` HTML.

## 6. Parquet file is not created until the first row group flushes

**Symptom.** You start a `planet` run with `--format parquet` and `./data/out.parquet` doesn't appear for several minutes.

**Cause.** `ParquetWriter.__enter__` doesn't touch the file. The file is only created on the first `_flush()`, which happens after `row_group_size` rows have accumulated.

**Workaround.** Wait. With the default `row_group_size=10_000` and dense tiles, the file appears within the first 1–2 tiles.

## 7. Resume requires identical bbox and tile grid

**Symptom.** You re-run `planet` with a different `--bbox` or `--tile-cols` and the checkpoint doesn't match; tiles are re-fetched from scratch.

**Cause.** Tile keys are derived from the bbox and grid:

```python
key = f"tile_{t_south:.6f}_{t_west:.6f}_{t_north:.6f}_{t_east:.6f}"
```

A different bbox or grid produces different keys, so the checkpoint file matches nothing.

**Workaround.** Always re-run with the exact same bbox and grid as the original. Or accept that a parameter change forces a full re-fetch.

## 8. GeoJSON coordinate order is `[lon, lat]`, not `[lat, lon]`

**Symptom.** Polygons appear in the wrong hemisphere or with longitude/latitude swapped.

**Cause.** RFC 7946 specifies `[lon, lat]`. Our internal model uses `(lat, lon)`. The conversion happens in `formats/geojson.py::_to_feature` and `formats/parquet.py::_to_row`.

**Mitigation.** Read [`architecture.md` § Coordinate conventions](./architecture.md#coordinate-conventions). If you add a new format, document the order you choose.

## 9. Relations have empty `geometry` and meaningful `members`

**Symptom.** A relation's `geometry` column in parquet is `null`/`[]`, even though the relation has area on the map.

**Cause.** `out geom;` for a relation returns the relation object plus its member ways, each of which may carry its own `geometry`. We store the member dicts as a JSON string in `members_json` (column `members_json`), not in the top-level `geometry` column.

**Workaround.** When you want polygon area for a relation, iterate `members_json` and concatenate the outer-ring geometries. `formats/geojson.py::_to_feature` already does this.

## 10. `hf sync` overwrites silently on size match, mtime mismatch

**Symptom.** You edit a local file (e.g. the map HTML) and `hf sync` does not upload the change because the size is the same and the mtime difference is below its threshold.

**Cause.** `hf sync` uses `(mtime, size)` as the change heuristic.

**Workaround.** Use `--ignore-times` if you want to force a size-only comparison:

```bash
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object --ignore-times
```

## 11. `python -m pytest` outside `uv` fails with `ModuleNotFoundError`

**Symptom.** `ModuleNotFoundError: No module named 'osm_tags_to_object'` when running tests with the system Python.

**Cause.** `pyproject.toml` declares `pythonpath = ["src"]` for pytest, but only `uv run pytest` uses the project venv.

**Workaround.** Always use `uv run pytest`, or set `PYTHONPATH=src` manually.

## 12. `data/` is gitignored but easy to forget about

**Symptom.** You commit changes; the data files don't appear. You `git status`; working tree is clean. You think your fetch didn't work.

**Cause.** `data/` is in `.gitignore`. Fetches write there on purpose.

**Workaround.** `ls -la data/` to confirm files exist; `hf sync --dry-run` to see what would be uploaded.

## 13. The `osm-tags-to-object` console script must be reinstalled after pulling new code

**Symptom.** You update the CLI (`cli.py`) but `osm-tags-to-object` still runs the old version.

**Cause.** The console script is installed from the project's `pyproject.toml` `[project.scripts]`. `uv sync` reinstalls it; `uv run` uses it directly.

**Workaround.** `uv sync` after pulling, or use `uv run osm-tags-to-object …` which builds a fresh venv-aware script invocation each time.
