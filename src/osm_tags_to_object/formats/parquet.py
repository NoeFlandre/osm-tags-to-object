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

DEFAULT_ROW_GROUP_SIZE = 10_000


class ParquetWriter:
    """Write OSM objects to a Parquet file as a stream of row groups.

    Rows are buffered in memory until ``row_group_size`` rows have
    accumulated (or until ``close``), at which point the buffer is
    flushed as one Parquet row group. This caps peak memory at
    ``row_group_size`` rows plus one in-flight row group.
    """

    def __init__(
        self,
        path: Path,
        row_group_size: int = DEFAULT_ROW_GROUP_SIZE,
    ) -> None:
        if row_group_size < 1:
            raise ValueError(f"row_group_size must be >= 1, got {row_group_size}")
        self._path = Path(path)
        self._row_group_size = row_group_size
        self._buffer: list[dict[str, Any]] = []
        self._writer: pq.ParquetWriter | None = None
        self._closed = False

    def __enter__(self) -> "ParquetWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, obj: OSMObject) -> None:
        if self._closed:
            raise RuntimeError("ParquetWriter is closed")
        self._buffer.append(_to_row(obj))
        if len(self._buffer) >= self._row_group_size:
            self._flush()

    def close(self) -> None:
        """Flush any buffered rows and close the underlying writer."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._writer is None and not self._buffer:
                # Zero writes ever: produce a valid empty file with our schema
                # so downstream readers still know what to expect.
                empty = pa.table({f.name: [] for f in _SCHEMA}, schema=_SCHEMA)
                pq.write_table(empty, str(self._path))
            else:
                self._flush()
        finally:
            if self._writer is not None:
                self._writer.close()
                self._writer = None

    def _flush(self) -> None:
        if not self._buffer:
            return
        table = pa.Table.from_pylist(self._buffer, schema=_SCHEMA)
        if self._writer is None:
            self._writer = pq.ParquetWriter(str(self._path), _SCHEMA)
        self._writer.write_table(table)
        self._buffer = []


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
