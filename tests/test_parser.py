from osm_tags_to_object.parser import parse_osm_elements


def test_parser_excludes_nodes():
    data = {
        "elements": [
            {"type": "node", "id": 1, "tags": {"amenity": "bench"}},
            {
                "type": "way",
                "id": 2,
                "tags": {"amenity": "bench"},
                "geometry": [
                    {"lat": 43.73, "lon": 7.42},
                    {"lat": 43.74, "lon": 7.43},
                    {"lat": 43.75, "lon": 7.44},
                ],
            },
        ]
    }
    objects = parse_osm_elements(data)
    assert len(objects) == 1
    obj = objects[0]
    assert obj.type == "way"
    assert obj.id == 2
    assert obj.tags == {"amenity": "bench"}
    assert obj.geometry == ((43.73, 7.42), (43.74, 7.43), (43.75, 7.44))


def test_parser_preserves_relations_with_members_and_member_geometry():
    data = {
        "elements": [
            {
                "type": "relation",
                "id": 99,
                "tags": {"type": "multipolygon", "landuse": "forest"},
                "members": [
                    {
                        "type": "way",
                        "ref": 1,
                        "role": "outer",
                        "geometry": [{"lat": 43.73, "lon": 7.42}],
                    },
                    {
                        "type": "way",
                        "ref": 2,
                        "role": "inner",
                        "geometry": [{"lat": 43.74, "lon": 7.43}],
                    },
                ],
            }
        ]
    }
    objects = parse_osm_elements(data)
    assert len(objects) == 1
    assert objects[0].type == "relation"
    assert objects[0].tags == {"type": "multipolygon", "landuse": "forest"}
    assert objects[0].members == (
        {"type": "way", "ref": 1, "role": "outer", "geometry": [{"lat": 43.73, "lon": 7.42}]},
        {"type": "way", "ref": 2, "role": "inner", "geometry": [{"lat": 43.74, "lon": 7.43}]},
    )
    # Relation itself has no top-level geometry
    assert objects[0].geometry == ()


def test_parser_handles_missing_tags():
    data = {
        "elements": [
            {"type": "way", "id": 1, "geometry": [{"lat": 43.7, "lon": 7.4}]}
        ]
    }
    objects = parse_osm_elements(data)
    assert objects[0].tags == {}


def test_parser_handles_missing_geometry():
    data = {"elements": [{"type": "way", "id": 1, "tags": {"amenity": "bench"}}]}
    objects = parse_osm_elements(data)
    assert objects[0].geometry == ()


def test_parser_returns_empty_list_when_no_elements():
    assert parse_osm_elements({"elements": []}) == []
