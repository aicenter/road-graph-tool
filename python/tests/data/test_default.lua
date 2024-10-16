local srid = 4326

local tables = {}

-- define table nodes:
tables.nodes = osm2pgsql.define_node_table('test_nodes', {
    -- not_null = true: if invalid node, ignore it
    { column = 'geom', type = 'point', projection=srid, not_null = true },
    { column = 'tags', type = 'jsonb' },
})

-- define table ways:
tables.ways = osm2pgsql.define_way_table('test_ways', {
    -- not_null = true: if invalid way, ignore it
    { column = 'geom', type = 'linestring', projection=srid, not_null = true },
    { column = 'tags', type = 'jsonb' },
    { column = 'nodes', type = 'jsonb' },
})


tables.relations = osm2pgsql.define_relation_table('test_relations', {
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


-- Process tagged objects:
function osm2pgsql.process_node(object)
    clean_tags(object.tags)

    tables.nodes:insert({
        geom = object:as_point(),
        tags = object.tags,
    })
end

function osm2pgsql.process_way(object)
    clean_tags(object.tags)

    tables.ways:insert({
        geom = object:as_linestring(),
        tags = object.tags,
        nodes = object.nodes,
    })
end

function osm2pgsql.process_relation(object)
    clean_tags(object.tags)

    tables.relations:insert({
        tags = object.tags,
        members = object.members,
    })
end


-- Process untagged objects:
function osm2pgsql.process_untagged_node(object)
    clean_tags(object.tags)

    tables.nodes:insert({
        geom = object:as_point(),
        tags = object.tags,
    })
end

function osm2pgsql.process_untagged_way(object)
    clean_tags(object.tags)

    tables.ways:insert({
        geom = object:as_linestring(),
        tags = object.tags,
        nodes = object.nodes,
    })
end

function osm2pgsql.process_untagged_relation(object)
    clean_tags(object.tags)

    tables.relations:insert({
        tags = object.tags,
        members = object.members,
    })
end