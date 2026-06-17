"""Persistent checkpoints for resumable long-running fetches.

A :class:`Checkpoint` tracks which work units have completed; an instance
of :class:`FileCheckpointStore` saves that set to disk so a crashed or
interrupted run can pick up where it left off.

The store writes atomically (temp file + rename) so a crash mid-write
never leaves a half-written file that would look like a corrupt checkpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class CheckpointStore(Protocol):
    """Persistence layer for a set of completed work-unit keys."""

    def load(self) -> set[str]: ...
    def save(self, completed: set[str]) -> None: ...


class FileCheckpointStore:
    """JSON-file backed :class:`CheckpointStore`.

    Writes are atomic: the new state goes to ``<path>.tmp`` first, then
    replaces ``<path>`` via :meth:`Path.replace` (which is atomic on POSIX).
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> set[str]:
        if not self._path.exists():
            return set()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            # Treat a corrupt file as empty so a botched run can recover.
            return set()
        if not isinstance(data, list):
            return set()
        return {str(x) for x in data}

    def save(self, completed: set[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(sorted(completed), indent=2), encoding="utf-8")
        tmp.replace(self._path)


class Checkpoint:
    """In-memory view of a :class:`CheckpointStore`.

    Every mutation is immediately persisted so that an interrupted run
    leaves a consistent checkpoint file behind.
    """

    def __init__(self, store: CheckpointStore) -> None:
        self._store = store
        self._completed: set[str] = set(store.load())

    @property
    def completed(self) -> frozenset[str]:
        return frozenset(self._completed)

    @property
    def count(self) -> int:
        return len(self._completed)

    def is_done(self, key: str) -> bool:
        return key in self._completed

    def mark_done(self, key: str) -> None:
        if key in self._completed:
            return
        self._completed.add(key)
        self._store.save(self._completed)

    def reset(self) -> None:
        """Forget all progress and persist the empty state."""
        self._completed.clear()
        self._store.save(self._completed)
