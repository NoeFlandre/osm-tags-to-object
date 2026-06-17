"""Parquet writer for OSM objects using pyarrow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ..models import OSMObject

_GEOMETRY_TYPE = pa.list_(
    pa.struct([("lat", pa.float64()), ("lon", pa.float64())])
)

_SCHEMA = pa.schema(
    [
        ("type", pa.string()),
        ("id", pa.int64()),
        ("tags", pa.map_(pa.string(), pa.string())),
        ("geometry", _GEOMETRY_TYPE),
        ("members_json", pa.string()),
    ]
)


class ParquetWriter:
    """Write OSM objects to a Parquet file.

    Objects are buffered in memory until ``close`` (called by ``__exit__``).
    Sufficient for the prototype; for very large jobs, swap in a row-group
    streaming implementation without changing the public API.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._rows: list[dict[str, Any]] = []
        self._closed = False

    def __enter__(self) -> "ParquetWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, obj: OSMObject) -> None:
        if self._closed:
            raise RuntimeError("ParquetWriter is closed")
        self._rows.append(_to_row(obj))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self._rows:
            # Write an empty table with the schema so the file is still valid.
            table = pa.table({f.name: [] for f in _SCHEMA}, schema=_SCHEMA)
        else:
            table = pa.Table.from_pylist(self._rows, schema=_SCHEMA)
        pq.write_table(table, self._path)


def _to_row(obj: OSMObject) -> dict[str, Any]:
    geometry = (
        [{"lat": lat, "lon": lon} for lat, lon in obj.geometry] if obj.geometry else None
    )
    return {
        "type": obj.type,
        "id": obj.id,
        "tags": list(obj.tags.items()),
        "geometry": geometry,
        "members_json": json.dumps(list(obj.members), ensure_ascii=False)
        if obj.members
        else None,
    }
