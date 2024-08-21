-- define tables' dictionary
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
		{ column = "area", type = "integer", create_only = true },
		{ column = "from", type = "bigint", not_null = true },
		{ column = "to", type = "bigint", not_null = true },
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
		{ column = "id", sql_type = "bigserial", create_only = true },
		-- { column = "way_id", type = "bigint" },
		{ column = "node_id", type = "bigint" },
		{ column = "position", type = "smallint" },
		{ column = "area", type = "smallint", create_only = true },
	},
})

-- Helper function to remove some of the tags.
-- Returns true if there are no tags left.
local function clean_tags(tags)
	tags.odbl = nil
	tags.created_by = nil
	tags.source = nil
	tags["source:ref"] = nil

	return next(tags) == nil
end

-- Process every node in the input
function osm2pgsql.process_node(object)
	-- if clean_tags(object.tags) then
	--     return
	-- end
	-- clean_tags(object.tags)
	-- no need to clean tags, as we do not pass them to db

	tables.nodes:insert({
		geom = object:as_point(),
		contracted = false,
	})
end

-- Process every way in the input
function osm2pgsql.process_way(object)
	-- if clean_tags(object.tags) then
	--     return
	-- end
	clean_tags(object.tags)

	local nodes = object.nodes
	-- add to ways
	tables.ways:insert({
		geom = object:as_linestring(), -- TODO: under question, scheme needs it to be simple geometry
		tags = object.tags, -- TODO: we may need to remove `oneway` tag as there is a column for that
		oneway = object.tags.oneway == "yes",
		-- nodes = object.nodes,
		from = nodes[1],
		to = nodes[#nodes],
	})

	-- add to nodes_ways
	for index, value in ipairs(nodes) do
		tables.nodes_ways:insert({
			-- way_id = object.id,
			node_id = value,
			position = index,
		})
	end
end

-- Process every relation in the input
function osm2pgsql.process_relation(object)
	if clean_tags(object.tags) then
		return
	end

	tables.relations:insert({
		tags = object.tags,
		members = object.members,
	})
end
