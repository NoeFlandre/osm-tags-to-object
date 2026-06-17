import json
from pathlib import Path

from osm_tags_to_object.checkpoint import Checkpoint, FileCheckpointStore


def test_checkpoint_starts_empty(tmp_path: Path):
    store = FileCheckpointStore(tmp_path / "cp.json")
    cp = Checkpoint(store)
    assert cp.count == 0
    assert cp.completed == frozenset()


def test_checkpoint_mark_done_adds_a_key(tmp_path: Path):
    store = FileCheckpointStore(tmp_path / "cp.json")
    cp = Checkpoint(store)
    cp.mark_done("tile_0_0")
    assert cp.is_done("tile_0_0")
    assert cp.count == 1


def test_checkpoint_mark_done_is_idempotent(tmp_path: Path):
    store = FileCheckpointStore(tmp_path / "cp.json")
    cp = Checkpoint(store)
    cp.mark_done("tile_0_0")
    cp.mark_done("tile_0_0")
    cp.mark_done("tile_0_0")
    assert cp.count == 1


def test_checkpoint_persists_across_instances(tmp_path: Path):
    path = tmp_path / "cp.json"
    Checkpoint(FileCheckpointStore(path)).mark_done("tile_1_2")
    Checkpoint(FileCheckpointStore(path)).mark_done("tile_3_4")

    fresh = Checkpoint(FileCheckpointStore(path))
    assert fresh.is_done("tile_1_2")
    assert fresh.is_done("tile_3_4")
    assert fresh.count == 2


def test_file_checkpoint_store_handles_missing_file(tmp_path: Path):
    store = FileCheckpointStore(tmp_path / "cp.json")
    assert store.load() == set()


def test_file_checkpoint_store_handles_corrupt_file(tmp_path: Path):
    path = tmp_path / "cp.json"
    path.write_text("not valid json {{{")
    store = FileCheckpointStore(path)
    # Corrupt files are treated as empty so a bad run can be recovered.
    assert store.load() == set()


def test_file_checkpoint_store_creates_parent_directory(tmp_path: Path):
    path = tmp_path / "nested" / "deeper" / "cp.json"
    Checkpoint(FileCheckpointStore(path)).mark_done("a")
    assert path.exists()


def test_file_checkpoint_store_writes_valid_json(tmp_path: Path):
    path = tmp_path / "cp.json"
    Checkpoint(FileCheckpointStore(path)).mark_done("tile_x")
    data = json.loads(path.read_text())
    assert data == ["tile_x"]


def test_checkpoint_reset_clears_state_and_persists(tmp_path: Path):
    path = tmp_path / "cp.json"
    cp = Checkpoint(FileCheckpointStore(path))
    cp.mark_done("a")
    cp.mark_done("b")
    cp.reset()
    assert cp.count == 0
    # New instance should also see empty.
    assert Checkpoint(FileCheckpointStore(path)).count == 0


def test_checkpoint_writes_are_atomic_no_partial_files(tmp_path: Path):
    """save() must not leave a half-written file on disk."""
    path = tmp_path / "cp.json"
    store = FileCheckpointStore(path)
    cp = Checkpoint(store)
    cp.mark_done("a")

    # No leftover .tmp files after a normal save.
    leftovers = list(path.parent.glob("*.tmp"))
    assert leftovers == []
    # The final file is valid JSON.
    json.loads(path.read_text())
