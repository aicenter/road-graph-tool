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

-- Helper function to remove some of the tags.
-- Returns true if there are no tags left.
local function clean_tags(tags)
    tags.odbl = nil
    tags.created_by = nil
    tags.source = nil
    tags['source:ref'] = nil

    return next(tags) == nil
end


-- Functions to process objects:
local function do_nodes(object)
    clean_tags(object.tags)

    tables.nodes:insert({
        geom = object:as_point(),
        tags = object.tags,
    })
end

local function do_ways(object)
    clean_tags(object.tags)

    tables.ways:insert({
        geom = object:as_linestring(),
        tags = object.tags,
        nodes = object.nodes,
    })
end

local function do_relations(object)
    clean_tags(object.tags)

    tables.relations:insert({
        tags = object.tags,
        members = object.members,
    })
end

-- Process tagged objects:
osm2pgsql.process_node = do_nodes
osm2pgsql.process_way = do_ways
osm2pgsql.process_relation = do_relations

-- If osm2pgsql is of version `2.0.0`, assign process_untagged_* functions:
if osm2pgsql.version == '2.0.0' then
    osm2pgsql.process_untagged_node = do_nodes
    osm2pgsql.process_untagged_way = do_ways
    osm2pgsql.process_untagged_relation = do_relations
end