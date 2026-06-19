# Milestones

What was built when, and what was learned. Read top-to-bottom to see the project grow.

## Milestone 0 — bootstrap

**Commit `62797f4`**. Initialize the project with `uv`, link to the GitHub repo `https://github.com/NoeFlandre/osm-tags-to-object.git`, add `pyproject.toml`, `main.py`, `.gitignore`, `.python-version`.

**Commit `96fecfc`**. Document the data-storage rule: everything lives on `hf://buckets/NoeFlandre/osm-tags-to-object`, not locally. `data/` is gitignored and used only as the staging area for `hf sync`.

**Lesson.** No code yet, but the boundary is fixed: `data/` is throwaway, the bucket is the source of truth.

## Milestone 1 — single-area prototype

**Commit `66e1af9`**. Five modules, 17 TDD tests, all green.

- `tags.py` — `TagFilter` dataclass.
- `query.py` — Overpass QL builder; never selects nodes; uses `out body; >; out skel qt;` to also fetch referenced nodes.
- `client.py` — `OverpassClient` over `httpx`.
- `parser.py` — Drops node elements; builds `OSMObject` with raw `nodes` as integer IDs.
- `models.py` — `OSMObject` with `type`, `id`, `tags`, `nodes`, `members`.
- `pipeline.py` — `fetch_matching_objects()`.
- `scripts/smoke.py` — Live end-to-end check (Monaco bbox, ~19 objects).

**Discoveries during smoke test.**

- **Public Overpass returns HTTP 406 to `python-httpx/...` User-Agent.** Fixed by sending a descriptive UA per request.
- **Public Overpass also returns 406 to `Accept: */*`.** Fixed by sending `Accept: application/json` per request.

These two fixes are the genesis of the explicit headers in `OverpassClient`. They live in `tests/test_client.py` (`test_client_sets_a_descriptive_user_agent`, `test_client_sets_accept_header_to_json`).

**Lesson.** Public Overpass has fragile header expectations. Document and test both.

## Milestone 2 — writers, retry, GeoJSON/Parquet, CLI, map, docs

**Commit `fef7c46`**. 44 new tests (61 total).

- Query switched to `out geom;` so each way's coordinates come back inline (no second pass for nodes; one HTTP request per area).
- `OSMObject` gained a `geometry: tuple[tuple[float, float], ...]` field; relations keep `members` dicts.
- `formats/geojson.py` — Streaming GeoJSON FeatureCollection writer.
- `formats/parquet.py` — Parquet writer via `pyarrow`.
- `storage.py` — `write_objects(iter, path, format)`.
- `retry.py` — Generic exponential-backoff helper, `Retry-After`-aware.
- `client.py` — Now wraps every fetch in `retry_with_backoff`.
- `cli.py` — Click group with `fetch` and `map` subcommands + spec parsers.
- `map.py` — Folium interactive map with hover tooltips and click popups.
- `pyproject.toml` — Real description, `[project.scripts]` installs `osm-tags-to-object`.
- `main.py` — Thin shim around `cli.cli`.
- `README.md` — Rewritten with quickstart, CLI reference, project layout, how-it-works, and the HF bucket workflow.

**Lesson.** The retry helper is generic on purpose — `OverpassClient` is the only place that knows about HTTP. Same for the writers (`FormatWriter` protocol); new formats can be added without touching the storage layer.

## Milestone 3 — checkpointing, planet fetch, streaming Parquet

**Commit `18adffb`**. 31 new tests (92 total).

- `checkpoint.py` — `Checkpoint` + `FileCheckpointStore`. Atomic writes (`.tmp` + rename); corrupt files treated as empty.
- `tiles.py` — `TileGrid` for deterministic bbox subdivision.
- `planet.py` — `fetch_planet()` tiled + checkpointed iteration.
- `formats/parquet.py` — Refactored to use `pyarrow.parquet.ParquetWriter` with bounded row-group buffering. Empty input still produces a valid file.
- `cli.py` — New `planet` subcommand with `--tile-rows`, `--tile-cols`, `--checkpoint`.
- `README.md` — Resumable planet fetch section, planet CLI reference.

**Design choice worth flagging.** Failure semantics: if a tile fetch raises, prior tiles stay marked done and the failing tile is left unmarked. The next resume retries exactly that tile. Verified by `test_fetch_planet_does_not_swallow_exceptions_but_keeps_checkpoint_intact`.

**Lesson.** "Resumable" is more than just "save state" — it requires thinking carefully about *when* to mark a unit complete. Mark-on-completion (not mark-on-start) is the right default.

## Milestone 4 — country-scale demonstration

**Commit `87378bb`** (on top of Milestone 3). Demonstrated the system at the scale of mainland France.

- Fetched every `landuse=forest` way + relation across France, tiled 9 × 14 = 126 tiles of ~1° each.
- Took ~38 minutes end-to-end with checkpoint + retry. Manually killed once mid-flight and resumed cleanly.
- Output: 640 MB Parquet with 889,480 polygons (847,122 ways + 42,358 relations), 89 row groups.
- `scripts/parquet_to_map_geojson.py` — converts parquet into folium-friendly GeoJSON: drops relations, keeps ways > 5 km² bbox, RDP-simplifies (~2% of vertices remain).
- Interactive map: 26 MB HTML with 6,026 polygons; hover any forest to see its OSM tags.

**Lessons.**

- **GeoJSON at country scale is a non-starter.** First attempt wrote directly to GeoJSON; at 26 tiles the file was already 265 MB. Killed and restarted with Parquet.
- **Folium can't render 890 K polygons.** Even after pre-filtering to 60 K, the HTML was 185 MB and the browser would hang. The two-stage filter (drop relations, bbox-area threshold, RDP simplify) brought the map to 6 K polygons / 26 MB.
- **The checkpoint actually saved a run.** We deliberately killed the first GeoJSON attempt and restarted with `--format parquet`. The 26 tiles already done were skipped on resume. This is the design being used for its intended purpose.

## Final docs pass

This file is part of the final docs commit, written so that a fresh coding agent can pick up the codebase without losing context.

**Files added.**

- `AGENTS.md` — Coding-agent orientation: module map, conventions, top gotchas.
- `docs/architecture.md` — Data flow diagram, data model, coordinate conventions, Parquet schema, extension points.
- `docs/operations.md` — Runbook: dev setup, single fetch, country fetch, tiling, resuming, making a map, HF sync, debugging.
- `docs/decisions.md` — *Why* the code is the way it is, with alternatives considered.
- `docs/gotchas.md` — Full list of traps with reproduction commands.
- `docs/milestones.md` (this file) — Project history.
- `README.md` — Updated to point at the new docs.

**Push + HF sync.** Pushed all six commits to `origin/master`. Ran `hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object` (uploaded 949 MB). Deleted local `./data/` per the project's no-data-on-disk rule.

## Test counts through the project

| Milestone | Cumulative tests |
|---|---|
| 1 | 17 |
| 2 | 61 |
| 3 | 92 |
| 4 | 92 (no new tests; new code is `parquet_to_map_geojson.py`, a one-off script) |

## Datasets produced

| Dataset | Size | Polygons | Status |
|---|---|---|---|
| France forests (parquet) | 640 MB | 889,480 | On HF bucket |
| France forests (map geojson) | 14 MB | 6,026 | On HF bucket |
| France forests (HTML map) | 26 MB | 6,026 | On HF bucket |
| France forests (checkpoint) | 6 KB | 126 tiles | On HF bucket |

Local `./data/` is empty; everything lives on `hf://buckets/NoeFlandre/osm-tags-to-object`.
