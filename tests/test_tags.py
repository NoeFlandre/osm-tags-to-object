from osm_tags_to_object.tags import TagFilter


def test_tagfilter_holds_a_single_key_value_pair():
    f = TagFilter({"amenity": "bench"})
    assert f.tags == {"amenity": "bench"}


def test_tagfilter_supports_multiple_values_for_same_key():
    f = TagFilter({"amenity": ["bench", "fountain"]})
    assert f.tags == {"amenity": ["bench", "fountain"]}
