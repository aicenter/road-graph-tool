from types import SimpleNamespace

import pytest
from shapely import geometry

from roadgraphtool.exceptions import ImportConflictError
from roadgraphtool.overpass_import import (
    _HIGHWAY_FILTER,
    _build_way_query,
    _car_direction,
    _configured_tag_keys,
    _new_nodes,
    _new_ways,
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


def test_car_direction_uses_oneway():
    for value in ("yes", "true", "1"):
        assert _car_direction([1, 2, 3], {"highway": "residential", "oneway": value}) == ([1, 2, 3], True)
    assert _car_direction([1, 2, 3], {"highway": "residential", "oneway": "-1"}) == ([3, 2, 1], True)
    assert _car_direction([1, 2, 3], {"highway": "residential"}) == ([1, 2, 3], False)


def test_car_direction_implied_oneway():
    assert _car_direction([1, 2, 3], {"highway": "primary", "junction": "roundabout"}) == ([1, 2, 3], True)
    assert _car_direction([1, 2, 3], {"highway": "motorway"}) == ([1, 2, 3], True)
    assert _car_direction([1, 2, 3], {"highway": "motorway_link"}) == ([1, 2, 3], False)


def test_car_direction_explicit_two_way_overrides_implied_oneway():
    assert _car_direction([1, 2, 3], {"highway": "motorway", "oneway": "no"}) == ([1, 2, 3], False)
    assert _car_direction([1, 2, 3], {"highway": "tertiary", "junction": "roundabout", "oneway": "no"}) == (
        [1, 2, 3],
        False,
    )


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


def test_new_nodes_skips_identical_existing_nodes():
    node_coord = {1: (14.4, 50.1), 2: (14.5, 50.2), 3: (14.6, 50.3)}

    # coordinates stored by another import may differ below the OSM precision
    new_nodes = _new_nodes(node_coord, {2: (14.5 + 1e-9, 50.2)})

    assert new_nodes == {1: (14.4, 50.1), 3: (14.6, 50.3)}


def test_new_nodes_rejects_existing_node_with_other_coordinates():
    node_coord = {1: (14.4, 50.1), 2: (14.5, 50.2)}

    with pytest.raises(ImportConflictError, match="1 imported nodes are already in the database .*: 2\\."):
        _new_nodes(node_coord, {1: (14.4, 50.1), 2: (14.5, 50.2001)})


def test_new_ways_skips_identical_existing_ways():
    ways = {10: {"nodes": [1, 2, 3], "oneway": True}, 11: {"nodes": [3, 4], "oneway": False}}

    new_ways = _new_ways(ways, {10: {"nodes": [1, 2, 3], "oneway": True}})

    assert new_ways == {11: {"nodes": [3, 4], "oneway": False}}


@pytest.mark.parametrize(
    "existing_way",
    [
        {"nodes": [1, 2], "oneway": True},  # other nodes
        {"nodes": [3, 2, 1], "oneway": True},  # other direction of the nodes
        {"nodes": [1, 2, 3], "oneway": False},  # other direction, e.g., from another network profile
        {"nodes": None, "oneway": True},  # way stored without nodes
    ],
)
def test_new_ways_rejects_existing_way_with_other_nodes_or_direction(existing_way):
    ways = {10: {"nodes": [1, 2, 3], "oneway": True}}

    with pytest.raises(ImportConflictError, match="1 imported ways are already in the database .*: 10\\."):
        _new_ways(ways, {10: existing_way})


def test_import_conflict_error_reports_the_first_conflicts_only():
    error = ImportConflictError("nodes", list(range(1, 14)), "coordinates")

    assert "13 imported nodes" in str(error)
    assert ": 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 and 3 more." in str(error)
    assert error.conflicts == list(range(1, 14))
