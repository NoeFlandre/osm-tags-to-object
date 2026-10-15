from __future__ import annotations

from typing import Protocol

from ..models import OSMObject


class FormatWriter(Protocol):
    """Streaming writer for a sequence of OSMObject.

    Implementations are context managers and accept objects one at a time
    so callers can stream from an HTTP response without materializing
    everything in memory.
    """

    def __enter__(self) -> "FormatWriter": ...
    def __exit__(self, *exc: object) -> None: ...
    def write(self, obj: OSMObject) -> None: ...
