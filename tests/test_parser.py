from osm_tags_to_object.parser import parse_osm_elements


def test_parser_excludes_nodes():
    data = {
        "elements": [
            {"type": "node", "id": 1, "tags": {"amenity": "bench"}},
            {
                "type": "way",
                "id": 2,
                "tags": {"amenity": "bench"},
                "nodes": [10, 11, 12],
            },
        ]
    }
    objects = parse_osm_elements(data)
    assert len(objects) == 1
    obj = objects[0]
    assert obj.type == "way"
    assert obj.id == 2
    assert obj.tags == {"amenity": "bench"}
    assert obj.nodes == (10, 11, 12)


def test_parser_preserves_relations_with_members():
    data = {
        "elements": [
            {
                "type": "relation",
                "id": 99,
                "tags": {"type": "multipolygon"},
                "members": [
                    {"type": "way", "ref": 1, "role": "outer"},
                    {"type": "way", "ref": 2, "role": "inner"},
                ],
            }
        ]
    }
    objects = parse_osm_elements(data)
    assert len(objects) == 1
    assert objects[0].type == "relation"
    assert objects[0].tags == {"type": "multipolygon"}
    assert objects[0].members == (
        {"type": "way", "ref": 1, "role": "outer"},
        {"type": "way", "ref": 2, "role": "inner"},
    )


def test_parser_handles_missing_tags():
    data = {"elements": [{"type": "way", "id": 1, "nodes": [1]}]}
    objects = parse_osm_elements(data)
    assert objects[0].tags == {}


def test_parser_returns_empty_list_when_no_elements():
    assert parse_osm_elements({"elements": []}) == []
