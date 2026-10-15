from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from .formats import open_writer
from .models import OSMObject

FormatName = Literal["geojson", "parquet"]


def write_objects(
    objects: Iterable[OSMObject],
    output_path: Path,
    format: FormatName,
) -> Path:
    """Stream ``objects`` to ``output_path`` in the given format.

    Parent directories are created. The caller is expected to pass an
    iterable that can be consumed lazily (e.g. a generator) so we never
    need to hold the whole dataset in memory.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open_writer(output_path, format) as writer:
        for obj in objects:
            writer.write(obj)
    return output_path
