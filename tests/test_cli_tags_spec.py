from osm_tags_to_object.cli import parse_tags_spec, parse_bbox_spec


def test_parse_tags_spec_single_key_value():
    assert parse_tags_spec("amenity=bench") == {"amenity": "bench"}


def test_parse_tags_spec_multiple_values_for_same_key():
    assert parse_tags_spec("amenity=bench,fountain") == {
        "amenity": ["bench", "fountain"]
    }


def test_parse_tags_spec_multiple_keys():
    assert parse_tags_spec("amenity=bench,highway=bus_stop") == {
        "amenity": "bench",
        "highway": "bus_stop",
    }


def test_parse_tags_spec_mixed():
    assert parse_tags_spec("amenity=bench,fountain,highway=bus_stop") == {
        "amenity": ["bench", "fountain"],
        "highway": "bus_stop",
    }


def test_parse_tags_spec_strips_whitespace():
    assert parse_tags_spec("amenity = bench , fountain") == {
        "amenity": ["bench", "fountain"]
    }


def test_parse_tags_spec_rejects_empty():
    import pytest

    with pytest.raises(ValueError):
        parse_tags_spec("")


def test_parse_tags_spec_rejects_value_with_no_preceding_key():
    import pytest

    with pytest.raises(ValueError):
        parse_tags_spec("bare_value")


def test_parse_bbox_spec():
    assert parse_bbox_spec("43.7,7.4,43.8,7.5") == (43.7, 7.4, 43.8, 7.5)


def test_parse_bbox_spec_strips_whitespace():
    assert parse_bbox_spec(" 43.7 , 7.4 , 43.8 , 7.5 ") == (43.7, 7.4, 43.8, 7.5)


def test_parse_bbox_spec_rejects_wrong_arity():
    import pytest

    with pytest.raises(ValueError):
        parse_bbox_spec("43.7,7.4,43.8")
