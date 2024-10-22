-- Dynamically determine directory path and update package.path
local separator = package.config:sub(1,1)
function get_directory_path(sep)
    local file_path = debug.getinfo(2, "S").source:sub(2)
    local dir_path = file_path:match("(.*" .. sep .. ")")
    return dir_path
end
local dir_path = get_directory_path(separator)
package.path = package.path .. ";" .. dir_path .. "?.lua"
local helper = require("helper")

local srid = 4326

local tables = {}

-- define table nodes:
tables.nodes = osm2pgsql.define_node_table('nodes', {
    { column = 'geom', type = 'point', projection=srid, not_null = true }, -- not_null = true: if invalid node, ignore it
    { column = 'tags', type = 'jsonb' },
})

-- define table ways:
tables.ways = osm2pgsql.define_way_table('ways', {
    { column = 'geom', type = 'linestring', projection=srid, not_null = true }, -- not_null = true: if invalid way, ignore it
    { column = 'tags', type = 'jsonb' },
    { column = 'nodes', type = 'jsonb' },
})

-- define table relations:
tables.relations = osm2pgsql.define_relation_table('relations', {
    { column = 'tags', type = 'jsonb' },
    { column = 'members', type = 'jsonb' },
})

-- Functions to process objects:
local function do_nodes(object)
    helper.clean_tags(object.tags)

    tables.nodes:insert({
        geom = object:as_point(),
        tags = object.tags,
    })
end

local function do_ways(object)
    helper.clean_tags(object.tags)

    tables.ways:insert({
        geom = object:as_linestring(),
        tags = object.tags,
        nodes = object.nodes,
    })
end

local function do_relations(object)
    helper.clean_tags(object.tags)

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
