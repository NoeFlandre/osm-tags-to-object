"""Command-line interface for ``osm-tags-to-object``.

Two subcommands:

* ``fetch`` - run an Overpass query for the given tags and stream the
  matching ways + relations to a GeoJSON or Parquet file under ``./data/``.
* ``map`` - turn a previously written GeoJSON file into an interactive
  Leaflet HTML map with polygon tooltips showing the OSM tags.
"""

from __future__ import annotations

from pathlib import Path

import click

from . import map as map_mod
from .checkpoint import Checkpoint, FileCheckpointStore
from .client import OverpassClient
from .pipeline import fetch_matching_objects
from .planet import fetch_planet
from .storage import write_objects
from .tags import TagFilter


# ---------------------------------------------------------------------------
# Spec parsers
# ---------------------------------------------------------------------------


def parse_tags_spec(spec: str) -> dict[str, str | list[str]]:
    """Parse a comma-separated tag spec into a dict.

    ``amenity=bench``                            -> {"amenity": "bench"}
    ``amenity=bench,fountain``                   -> {"amenity": ["bench", "fountain"]}
    ``amenity=bench,highway=bus_stop``           -> {"amenity": "bench", "highway": "bus_stop"}
    ``amenity=bench,fountain,highway=bus_stop``  -> {"amenity": ["bench", "fountain"],
                                                    "highway": "bus_stop"}
    """
    spec = spec.strip()
    if not spec:
        raise ValueError("tag spec is empty")

    result: dict[str, str | list[str]] = {}
    current_key: str | None = None
    for raw_piece in spec.split(","):
        piece = raw_piece.strip()
        if not piece:
            continue
        if "=" in piece:
            key, _, value = piece.partition("=")
            key = key.strip()
            value = value.strip()
            if not key or not value:
                raise ValueError(f"invalid tag fragment: {raw_piece!r}")
            current_key = key
            existing = result.get(key)
            if existing is None:
                result[key] = value
            elif isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]
        else:
            if current_key is None:
                raise ValueError(
                    f"value {piece!r} has no preceding key (use key=value,value)"
                )
            existing = result[current_key]
            if isinstance(existing, list):
                existing.append(piece)
            else:
                result[current_key] = [existing, piece]
    if not result:
        raise ValueError("tag spec did not contain any key=value pairs")
    return result


def parse_bbox_spec(spec: str) -> tuple[float, float, float, float]:
    """Parse ``south,west,north,east`` into a 4-tuple of floats."""
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 4:
        raise ValueError(f"bbox must have 4 comma-separated values, got {len(parts)}")
    try:
        return float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
    except ValueError as exc:
        raise ValueError(f"bbox values must be numeric: {spec!r}") from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Download OSM ways + relations that match a set of tags."""


@cli.command("fetch")
@click.option(
    "--tags",
    required=True,
    help="Comma-separated tag spec, e.g. 'amenity=bench,fountain,highway=bus_stop'.",
)
@click.option(
    "--bbox",
    default=None,
    help="Bounding box as south,west,north,east. Omit for planet-wide.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["geojson", "parquet"]),
    default="geojson",
    show_default=True,
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output file path. Parent directories are created.",
)
@click.option(
    "--endpoint",
    default=OverpassClient.DEFAULT_URL,
    show_default=True,
    help="Overpass API endpoint URL.",
)
def fetch_cmd(
    tags: str, bbox: str | None, fmt: str, output: str, endpoint: str
) -> None:
    """Fetch OSM objects matching the given tags and stream them to a file."""
    filter_tags = parse_tags_spec(tags)
    bbox_tuple = parse_bbox_spec(bbox) if bbox else None
    filter_obj = TagFilter(filter_tags)
    output_path = Path(output)

    click.echo(
        f"Fetching tags={filter_tags} bbox={bbox_tuple} via {endpoint} ..."
    )
    with OverpassClient(url=endpoint) as client:
        objects = fetch_matching_objects(filter_obj, bbox=bbox_tuple, client=client)
    click.echo(f"Got {len(objects)} matching objects; writing to {output_path} ...")
    write_objects(objects, output_path, format=fmt)
    click.echo(f"Done: {output_path}")


@cli.command("map")
@click.option(
    "--input",
    "-i",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Input GeoJSON file produced by ``fetch``.",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output HTML file.",
)
def map_cmd(input: Path, output: Path) -> None:
    """Render an interactive map of polygons from a GeoJSON file."""
    map_mod.render_map(input, output)
    click.echo(f"Map written to {output}")


@cli.command("planet")
@click.option(
    "--tags",
    required=True,
    help="Comma-separated tag spec, e.g. 'amenity=bench,fountain'.",
)
@click.option(
    "--bbox",
    required=True,
    help="Bounding box as south,west,north,east.",
)
@click.option(
    "--tile-rows",
    default=4,
    show_default=True,
    type=int,
    help="Number of rows to split the bbox into.",
)
@click.option(
    "--tile-cols",
    default=4,
    show_default=True,
    type=int,
    help="Number of columns to split the bbox into.",
)
@click.option(
    "--checkpoint",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to a checkpoint file. Re-running with the same path resumes.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["geojson", "parquet"]),
    default="geojson",
    show_default=True,
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output file path. Parent directories are created.",
)
@click.option(
    "--endpoint",
    default=OverpassClient.DEFAULT_URL,
    show_default=True,
    help="Overpass API endpoint URL.",
)
def planet_cmd(
    tags: str,
    bbox: str,
    tile_rows: int,
    tile_cols: int,
    checkpoint: Path,
    fmt: str,
    output: Path,
    endpoint: str,
) -> None:
    """Fetch a large region tile-by-tile with checkpointing for resumability."""
    filter_tags = parse_tags_spec(tags)
    bbox_tuple = parse_bbox_spec(bbox)
    output_path = Path(output)

    cp = Checkpoint(FileCheckpointStore(checkpoint))
    total = tile_rows * tile_cols
    click.echo(
        f"Fetching tags={filter_tags} bbox={bbox_tuple} tiled "
        f"{tile_rows}x{tile_cols} ({total} tiles) via {endpoint}"
    )
    click.echo(f"Resuming from checkpoint {checkpoint}: {cp.count}/{total} tiles done")

    with OverpassClient(url=endpoint) as client:
        objects = fetch_planet(
            filter_tags,
            bbox_tuple,
            cp,
            tile_rows=tile_rows,
            tile_cols=tile_cols,
            client=client,
        )
        write_objects(objects, output_path, format=fmt)

    click.echo(f"Done: {cp.count}/{total} tiles done; wrote {output_path}")


if __name__ == "__main__":
    cli()
