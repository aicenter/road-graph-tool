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
	ids = { type = "node", id_column = "id" },
	columns = {
		{ column = "geom", type = "point", not_null = true, projection = srid },
		{ column = "contracted", type = "boolean", not_null = true },
		{ column = "area", type = "integer", create_only = true },
	},
})

tables.ways = osm2pgsql.define_table({
	name = "ways",
	ids = { type = "way", id_column = "id" },
	columns = {
		{ column = "tags", type = "hstore" },
		{ column = "geom", type = "geometry", not_null = true, projection = srid },
		{ column = "area", type = "smallint", create_only = true },
		{ column = "from", type = "integer", not_null = true },
		{ column = "to", type = "integer", not_null = true },
		{ column = "oneway", type = "boolean" },
	},
})

tables.relations = osm2pgsql.define_table({
	name = "relations",
	ids = { type = "relation", id_column = "id" },
	columns = {
		{ column = "tags", type = "hstore" },
		{ column = "members", type = "jsonb" },
	},
})

tables.nodes_ways = osm2pgsql.define_table({
	name = "nodes_ways",
	ids = { type = "way", id_column = "way_id" },
	columns = {
		{ column = "id", sql_type = "serial", create_only = true },
		{ column = "node_id", type = "integer" },
		{ column = "position", type = "smallint" },
		{ column = "area", type = "smallint", create_only = true },
	},
})

-- Functions to process objects:
local function do_nodes(object)
	tables.nodes:insert({
		geom = object:as_point(),
		contracted = false,
	})
end

local function do_ways(object)
	helper.clean_tags(object.tags)

	local nodes = object.nodes

	local oneway = object.tags.oneway == "yes"

	-- clean additional tags
	object.tags.oneway = nil

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