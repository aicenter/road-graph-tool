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

-- Functions to process objects:
local function do_nodes(object)
    helper.clean_tags(object.tags)

    tables.nodes:insert({
        geom = object:as_point(),
        tags = object.tags,
    })
end

-- Process tagged objects:
osm2pgsql.process_node = do_nodes

-- If osm2pgsql is of version `2.0.0` or higher, assign process_untagged_* functions:
if helper.compare_version(osm2pgsql.version, '2.0.0') then
    osm2pgsql.process_untagged_node = do_nodes
end
