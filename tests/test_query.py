import re

from osm_tags_to_object.query import build_overpass_query
from osm_tags_to_object.tags import TagFilter


def test_query_for_single_tag_excludes_nodes():
    q = build_overpass_query(TagFilter({"amenity": "bench"}))
    assert "way[" in q
    assert "relation[" in q
    assert '["amenity"="bench"]' in q
    # Nodes must never be requested
    assert "node[" not in q


def test_query_with_multiple_values_for_same_key():
    q = build_overpass_query(TagFilter({"amenity": ["bench", "fountain"]}))
    assert '["amenity"="bench"]' in q
    assert '["amenity"="fountain"]' in q
    # Each (key, value) pair appears once for way and once for relation
    assert q.count('["amenity"="bench"]') == 2
    assert q.count('["amenity"="fountain"]') == 2


def test_query_with_multiple_keys():
    q = build_overpass_query(
        TagFilter({"amenity": "bench", "highway": "bus_stop"})
    )
    assert '["amenity"="bench"]' in q
    assert '["highway"="bus_stop"]' in q


def test_query_with_bbox_uses_bbox_filter():
    bbox = (43.7, 7.4, 43.8, 7.5)
    q = build_overpass_query(TagFilter({"amenity": "bench"}), bbox=bbox)
    assert "(43.7,7.4,43.8,7.5)" in q


def test_query_without_bbox_is_planet_wide():
    q = build_overpass_query(TagFilter({"amenity": "bench"}))
    # No numeric coordinate bbox in the query
    assert not re.search(r"\(\d+\.?\d*,\d+\.?\d*,\d+\.?\d*,\d+\.?\d*\)", q)
