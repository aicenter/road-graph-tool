"""Tests of the osm2pgsql style lua_styles/pedestrian.lua, run in an embedded Lua with a mocked osm2pgsql.

Requires the optional ``lupa`` package; skipped otherwise.
"""
from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")

STYLE_PATH = Path(__file__).resolve().parent.parent / "lua_styles" / "pedestrian.lua"

_MOCK_OSM2PGSQL = """
osm2pgsql = { version = "2.0.0", tables = {} }

function osm2pgsql.define_table(definition)
    local t = { rows = {} }
    function t:insert(row)
        table.insert(self.rows, row)
    end
    osm2pgsql.tables[definition.name] = t
    return t
end

function make_way(tags, nodes)
    return {
        tags = tags,
        nodes = nodes,
        as_linestring = function(self) return "linestring" end,
    }
end
"""


@pytest.fixture
def lua():
    runtime = lupa.LuaRuntime()
    runtime.execute(_MOCK_OSM2PGSQL)
    runtime.execute(f"dofile({str(STYLE_PATH.as_posix())!r})")
    return runtime


def _process_way(lua, tags: dict, nodes=(1, 2, 3)) -> list[dict]:
    """Run the style on one way and return the inserted ``ways`` rows."""
    way = lua.globals().make_way(lua.table_from(tags), lua.table_from(list(nodes)))
    lua.globals().osm2pgsql.process_way(way)
    rows = lua.globals().osm2pgsql.tables["ways"].rows
    return [dict(rows[i + 1]) for i in range(len(rows))]


def _nodes_ways(lua) -> list[int]:
    rows = lua.globals().osm2pgsql.tables["nodes_ways"].rows
    return [rows[i + 1]["node_id"] for i in range(len(rows))]


@pytest.mark.parametrize(
    "tags, walkable",
    [
        ({"highway": "footway"}, True),
        ({"highway": "steps"}, True),
        ({"highway": "residential"}, True),
        ({"highway": "service", "service": "parking_aisle"}, True),
        ({"highway": "footway", "foot": "no"}, False),
        ({"highway": "service", "access": "private"}, False),
        ({"highway": "service", "access": "private", "foot": "yes"}, True),
        ({"highway": "path", "access": "no", "foot": "designated"}, True),
        ({"highway": "residential", "access": "private", "foot": "private"}, False),
        ({"highway": "motorway"}, False),
        ({"highway": "trunk", "foot": "permissive"}, False),
        ({"highway": "trunk", "foot": "yes"}, True),
        ({"highway": "pedestrian", "area": "yes"}, False),
        ({"highway": "construction"}, False),
        ({"building": "yes"}, False),
        ({}, False),
    ],
)
def test_way_walkability(lua, tags, walkable):
    assert (len(_process_way(lua, tags)) == 1) == walkable


def test_car_oneway_is_ignored(lua):
    rows = _process_way(lua, {"highway": "residential", "oneway": "yes"})

    assert rows[0]["oneway"] is False
    assert (rows[0]["from"], rows[0]["to"]) == (1, 3)


def test_oneway_foot(lua):
    rows = _process_way(lua, {"highway": "footway", "oneway:foot": "yes"})

    assert rows[0]["oneway"] is True
    assert (rows[0]["from"], rows[0]["to"]) == (1, 3)


def test_oneway_foot_reversed(lua):
    rows = _process_way(lua, {"highway": "footway", "oneway:foot": "-1"})

    assert rows[0]["oneway"] is True
    assert (rows[0]["from"], rows[0]["to"]) == (3, 1)
    assert _nodes_ways(lua) == [3, 2, 1]
