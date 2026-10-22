from types import SimpleNamespace

from shapely import geometry

from roadgraphtool.overpass_import import (
    _HIGHWAY_FILTER,
    _build_way_query,
    _configured_tag_keys,
    _pedestrian_direction,
    _poly_to_overpass_arg,
    _tag_rows,
)

_SQUARE = geometry.Polygon([(14.40, 50.08), (14.41, 50.08), (14.41, 50.09), (14.40, 50.08)])


def test_car_way_query_is_unchanged():
    # the query as built before network profiles were introduced
    expected = f"""
[out:json][timeout:25];
(
        way[{_HIGHWAY_FILTER}](poly:"{_poly_to_overpass_arg(_SQUARE)}");
);
(._;>;);
out body;
"""

    assert _build_way_query([_SQUARE], 25, "car") == expected


def test_pedestrian_way_query_selects_walkable_ways():
    query = _build_way_query([_SQUARE], 25, "pedestrian")
    way_lines = [line.strip() for line in query.splitlines() if line.strip().startswith("way")]

    assert len(way_lines) == 3
    general, foot_allowed, motor = way_lines
    for highway in ("footway", "steps", "pedestrian", "path", "residential", "service"):
        assert highway in general
    assert '[foot!~"^(no|private)$"]' in general
    assert '[access!~"^(no|private)$"]' in general
    assert '[foot~"^(yes|designated|permissive)$"]' in foot_allowed
    assert "motorway" not in general
    assert '[highway~"^(motorway|motorway_link|trunk|trunk_link)$"]' in motor
    assert '[foot~"^(yes|designated)$"]' in motor
    assert all("[area!=yes]" in line for line in way_lines)


def test_pedestrian_way_query_one_statement_per_selector_and_polygon():
    other = geometry.Polygon([(14.50, 50.08), (14.51, 50.08), (14.51, 50.09), (14.50, 50.08)])

    query = _build_way_query([_SQUARE, other], 25, "pedestrian")

    assert sum(line.strip().startswith("way") for line in query.splitlines()) == 6


def test_pedestrian_direction_ignores_car_oneway():
    assert _pedestrian_direction([1, 2, 3], {"oneway": "yes"}) == ([1, 2, 3], False)
    assert _pedestrian_direction([1, 2, 3], {"oneway": "-1"}) == ([1, 2, 3], False)


def test_pedestrian_direction_uses_oneway_foot():
    assert _pedestrian_direction([1, 2, 3], {"oneway:foot": "yes"}) == ([1, 2, 3], True)
    assert _pedestrian_direction([1, 2, 3], {"oneway:foot": "-1"}) == ([3, 2, 1], True)
    assert _pedestrian_direction([1, 2, 3], {"oneway:foot": "no"}) == ([1, 2, 3], False)


def test_configured_tag_keys_defaults_to_empty():
    config = SimpleNamespace()

    assert _configured_tag_keys(config) == []


def test_configured_tag_keys_normalizes_and_deduplicates():
    config = SimpleNamespace(
        road_import=SimpleNamespace(tags=["highway", "name", "highway", None, ""])
    )

    assert _configured_tag_keys(config) == ["highway", "name"]


def test_tag_rows_keeps_configured_tags_for_inserted_elements_only():
    elements = [
        {"id": 1, "tags": {"highway": "residential", "name": "Main St", "surface": "asphalt"}},
        {"id": 2, "tags": {"highway": "service"}},
        {"id": 3, "tags": {"name": "Skipped"}},
    ]

    rows = _tag_rows(
        elements,
        "way_id",
        {"highway": 10, "name": 11},
        allowed_ids={1, 3},
    )

    assert rows == [
        {"way_id": 1, "tag_id": 10, "tag_value": "residential"},
        {"way_id": 1, "tag_id": 11, "tag_value": "Main St"},
        {"way_id": 3, "tag_id": 11, "tag_value": "Skipped"},
    ]
