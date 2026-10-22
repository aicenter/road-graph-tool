-- osm2pgsql flex style for the pedestrian network profile (road_import.profile: pedestrian).
--
-- Produces the same tables and columns as pipeline.lua, so the post-processing in process_osm.py works unchanged.
-- Differences from pipeline.lua:
--   * only ways walkable by a pedestrian are imported (see is_walkable),
--   * the direction of a way is taken from `oneway:foot` only; the car `oneway` tag is ignored.
--
-- The walkability rules must stay in sync with _WAY_SELECTORS in src/roadgraphtool/overpass_import.py
-- and with the README section "Pedestrian profile".

-- Dynamically determine directory path and update package.path
function get_directory_path()
    -- Get the file path of the currently executing script
    local file_path = debug.getinfo(2, "S").source:sub(2)

    -- Match up to the last directory separator (either / or \)
    local dir_path = file_path:match("(.*[\\/])")

    return dir_path
end

local dir_path = get_directory_path()
package.path = package.path .. ";" .. dir_path .. "?.lua"

local helper = require("helper")

local tables = {}

local srid = 4326

tables.nodes = osm2pgsql.define_table({
    name = "nodes",
    indexes = {},
    cluster = "no",
    ids = { type = "node", id_column = "id" },
    columns = {
        { column = "tags", type = "hstore" },
        { column = "geom", type = "point", not_null = true, projection = srid },
    },
})

tables.ways = osm2pgsql.define_table({
    name = "ways",
    indexes = {},
    cluster = "no",
    ids = { type = "way", id_column = "id" },
    columns = {
        { column = "tags",   type = "hstore" },
        { column = "geom",   type = "geometry", not_null = true, projection = srid },
        { column = "from",   type = "bigint",   not_null = true },
        { column = "to",     type = "bigint",   not_null = true },
        { column = "oneway", type = "boolean" },
    },
})

tables.relations = osm2pgsql.define_table({
    name = "relations",
    indexes = {},
    cluster = "no",
    ids = { type = "relation", id_column = "id" },
    columns = {
        { column = "tags",    type = "hstore" },
        { column = "members", type = "jsonb" },
    },
})

tables.nodes_ways = osm2pgsql.define_table({
    name = "nodes_ways",
    indexes = {},
    cluster = "no",
    ids = { type = "way", id_column = "way_id" },
    columns = {
        { column = "node_id",  type = "bigint" },
        { column = "position", type = "smallint" },
    },
})

-- Walkability rules
local function set(list)
    local result = {}
    for _, value in ipairs(list) do
        result[value] = true
    end
    return result
end

-- way classes walkable unless walking or access is forbidden
local pedestrian_highways = set({
    "footway", "pedestrian", "path", "steps", "living_street", "residential", "service", "unclassified",
    "tertiary", "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
    "track", "cycleway", "corridor", "bridleway",
})
-- way classes walkable only where walking is explicitly allowed
local motor_highways = set({ "motorway", "motorway_link", "trunk", "trunk_link" })

local forbidden = set({ "no", "private" })
local foot_allowed = set({ "yes", "designated", "permissive" })
local foot_allowed_on_motor_highways = set({ "yes", "designated" })

local function is_walkable(tags)
    local highway = tags.highway
    if highway == nil or tags.area == "yes" then
        return false
    end
    if motor_highways[highway] then
        return foot_allowed_on_motor_highways[tags.foot] == true
    end
    if not pedestrian_highways[highway] then
        return false
    end
    if foot_allowed[tags.foot] then
        return true
    end
    if forbidden[tags.foot] then
        return false
    end
    return not forbidden[tags.access]
end

-- Functions to process objects:
local function do_nodes(object)
    tables.nodes:insert({
        tags = object.tags,
        geom = object:as_point(),
    })
end

local function array_reverse(x)
    local n, m = #x, #x / 2
    for i = 1, m do
        x[i], x[n - i + 1] = x[n - i + 1], x[i]
    end
    return x
end

local function do_ways(object)
    if not is_walkable(object.tags) then
        return
    end

    helper.clean_tags(object.tags)

    local nodes = object.nodes
    local oneway = false

    local oneway_foot = object.tags["oneway:foot"]
    if oneway_foot == "-1" then
        -- handle reversed oneway way
        nodes = array_reverse(nodes)
        oneway = true
    else
        oneway = oneway_foot == "yes"
    end

    -- add to ways
    tables.ways:insert({
        geom = object:as_linestring(),
        tags = object.tags,
        oneway = oneway,
        from = nodes[1],
        to = nodes[#nodes],
    })

    -- add to nodes_ways
    for index, value in ipairs(nodes) do
        tables.nodes_ways:insert({
            node_id = value,
            position = index,
        })
    end
end

local function do_relations(object)
    if helper.clean_tags(object.tags) then
        return
    end
    tables.relations:insert({
        tags = object.tags,
        members = object.members,
    })
end

-- Process tagged objects:
osm2pgsql.process_node = do_nodes
osm2pgsql.process_way = do_ways
osm2pgsql.process_relation = do_relations

-- If osm2pgsql is of version `2.0.0` or higher, assign process_untagged_* functions:
if helper.compare_version(osm2pgsql.version, '2.0.0') then
    osm2pgsql.process_untagged_node = do_nodes
    osm2pgsql.process_untagged_way = do_ways
    osm2pgsql.process_untagged_relation = do_relations
end
