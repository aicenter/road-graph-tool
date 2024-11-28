-- Dynamically determine directory path and update package.path
local separator = package.config:sub(1, 1)
function get_directory_path(sep)
    local file_path = debug.getinfo(2, "S").source:sub(2)
    local dir_path = file_path:match("(.*" .. sep .. ")")
    return dir_path
end

local dir_path = get_directory_path(separator)
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
    helper.clean_tags(object.tags)

    local nodes = object.nodes
    local oneway = false

    if object.tags.oneway == "-1" then
        --         handle reversed oneway street
        nodes = array_reverse(nodes)
        oneway = true
    else
        oneway = object.tags.oneway == "yes"
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
