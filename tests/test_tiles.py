import pytest

from osm_tags_to_object.tiles import Tile, TileGrid


def test_tile_grid_single_tile_returns_unchanged_bbox():
    bbox = (43.7, 7.4, 43.8, 7.5)
    grid = TileGrid(bbox, rows=1, cols=1)
    tiles = list(grid)
    assert len(tiles) == 1
    assert tiles[0].bbox == bbox
    assert tiles[0].row == 0
    assert tiles[0].col == 0


def test_tile_grid_2x2_produces_4_non_overlapping_tiles_covering_the_bbox():
    bbox = (43.0, 7.0, 45.0, 9.0)
    grid = TileGrid(bbox, rows=2, cols=2)
    tiles = list(grid)
    assert len(tiles) == 4

    for tile in tiles:
        south, west, north, east = tile.bbox
        assert round(north - south, 6) == 1.0
        assert round(east - west, 6) == 1.0

    total_area = sum(
        (n - s) * (e - w) for s, w, n, e in (t.bbox for t in tiles)
    )
    original_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    assert round(total_area, 9) == round(original_area, 9)


def test_tile_grid_keys_are_unique_and_deterministic():
    bbox = (43.0, 7.0, 44.0, 8.0)
    grid = TileGrid(bbox, rows=2, cols=3)
    keys = [t.key for t in grid]
    assert len(keys) == len(set(keys))
    assert keys == [t.key for t in TileGrid(bbox, rows=2, cols=3)]


def test_tile_grid_length_matches_rows_times_cols():
    grid = TileGrid((0, 0, 1, 1), rows=4, cols=5)
    assert len(grid) == 20


def test_tile_grid_horizontal_split_only():
    bbox = (43.0, 7.0, 44.0, 9.0)
    grid = TileGrid(bbox, rows=1, cols=3)
    tiles = list(grid)
    assert len(tiles) == 3
    assert {t.bbox[0] for t in tiles} == {43.0}
    assert {t.bbox[2] for t in tiles} == {44.0}
    wests = sorted(t.bbox[1] for t in tiles)
    assert wests == [7.0, pytest.approx(7.666666666666667), pytest.approx(8.333333333333334)]


def test_tile_grid_vertical_split_only():
    bbox = (43.0, 7.0, 46.0, 8.0)
    grid = TileGrid(bbox, rows=3, cols=1)
    tiles = list(grid)
    assert len(tiles) == 3
    assert {t.bbox[1] for t in tiles} == {7.0}
    assert {t.bbox[3] for t in tiles} == {8.0}


def test_tile_grid_assigns_row_col_coordinates():
    bbox = (0.0, 0.0, 2.0, 2.0)
    grid = TileGrid(bbox, rows=2, cols=2)
    coords = {(t.row, t.col) for t in grid}
    assert coords == {(0, 0), (0, 1), (1, 0), (1, 1)}


def test_tile_grid_rejects_non_positive_dimensions():
    import pytest

    bbox = (0.0, 0.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        TileGrid(bbox, rows=0, cols=1)
    with pytest.raises(ValueError):
        TileGrid(bbox, rows=1, cols=0)
