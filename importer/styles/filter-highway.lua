-- Process nodes, ways, relations with highway tag

local tables = {}

-- define table nodes:
tables.nodes = osm2pgsql.define_node_table('nodes', {
    -- not_null = true: if invalid node, ignore it
    { column = 'geom', type = 'point', not_null = true },
    { column = 'tags', type = 'jsonb' },
    { column = 'type', type = 'text', not_null = true},
})


tables.ways = osm2pgsql.define_way_table('ways', {
    { column = 'name', type = 'text' },
    { column = 'type', type = 'text', not_null = true },
    { column = 'oneway', type = 'direction' },
    { column = 'maxspeed', type = 'int' },
    { column = 'lit', type = 'bool' },
    { column = 'tags', type = 'jsonb' },
    { column = 'nodes', type = 'jsonb' },
    { column = 'geom', type = 'linestring', not_null = true },
})


tables.relations = osm2pgsql.define_relation_table('relations', {
    { column = 'tags', type = 'jsonb' },
    { column = 'type', type = 'text', not_null = true },
    { column = 'members', type = 'jsonb' },
})


local delete_keys = {
    -- "mapper" keys
    'attribution',
    'comment',
    'created_by',
    'fixme',
    'note',
    'note:*',
    'odbl',
    'odbl:note',
    'source',
    'source:*',
    'source_ref',

    -- "import" keys

    -- Corine Land Cover (CLC) (Europe)
    'CLC:*',

    -- Geobase (CA)
    'geobase:*',
    -- CanVec (CA)
    'canvec:*',

    -- osak (DK)
    'osak:*',
    -- kms (DK)
    'kms:*',

    -- ngbe (ES)
    -- See also note:es and source:file above
    'ngbe:*',

    -- Friuli Venezia Giulia (IT)
    'it:fvg:*',

    -- KSJ2 (JA)
    -- See also note:ja and source_ref above
    'KSJ2:*',
    -- Yahoo/ALPS (JA)
    'yh:*',

    -- LINZ (NZ)
    'LINZ2OSM:*',
    'linz2osm:*',
    'LINZ:*',
    'ref:linz:*',

    -- WroclawGIS (PL)
    'WroclawGIS:*',
    -- Naptan (UK)
    'naptan:*',

    -- TIGER (US)
    'tiger:*',
    -- GNIS (US)
    'gnis:*',
    -- National Hydrography Dataset (US)
    'NHD:*',
    'nhd:*',
    -- mvdgis (Montevideo, UY)
    'mvdgis:*',

    -- EUROSHA (Various countries)
    'project:eurosha_2012',

    -- UrbIS (Brussels, BE)
    'ref:UrbIS',

    -- NHN (CA)
    'accuracy:meters',
    'sub_sea:type',
    'waterway:type',
    -- StatsCan (CA)
    'statscan:rbuid',

    -- RUIAN (CZ)
    'ref:ruian:addr',
    'ref:ruian',
    'building:ruian:type',
    -- DIBAVOD (CZ)
    'dibavod:id',
    -- UIR-ADR (CZ)
    'uir_adr:ADRESA_KOD',

    -- GST (DK)
    'gst:feat_id',

    -- Maa-amet (EE)
    'maaamet:ETAK',
    -- FANTOIR (FR)
    'ref:FR:FANTOIR',

    -- 3dshapes (NL)
    '3dshapes:ggmodelk',
    -- AND (NL)
    'AND_nosr_r',

    -- OPPDATERIN (NO)
    'OPPDATERIN',
    -- Various imports (PL)
    'addr:city:simc',
    'addr:street:sym_ul',
    'building:usage:pl',
    'building:use:pl',
    -- TERYT (PL)
    'teryt:simc',

    -- RABA (SK)
    'raba:id',
    -- DCGIS (Washington DC, US)
    'dcgis:gis_id',
    -- Building Identification Number (New York, US)
    'nycdoitt:bin',
    -- Chicago Building Inport (US)
    'chicago:building_id',
    -- Louisville, Kentucky/Building Outlines Import (US)
    'lojic:bgnum',
    -- MassGIS (Massachusetts, US)
    'massgis:way_id',
    -- Los Angeles County building ID (US)
    'lacounty:*',
    -- Address import from Bundesamt für Eich- und Vermessungswesen (AT)
    'at_bev:addr_date',

    -- misc
    'import',
    'import_uuid',
    'OBJTYPE',
    'SK53_bulk:load',
    'mml:class'
}

-- Returns true if there are no tags left.
local clean_tags = osm2pgsql.make_clean_tags_func(delete_keys)


-- HIGHWAY:

local highway_types = {
    'motorway',
    'motorway_link',
    'trunk',
    'trunk_link',
    'primary',
    'primary_link',
    'secondary',
    'secondary_link',
    'tertiary',
    'tertiary_link',
    'unclassified',
    'residential',
    'track',
    'service',
}

-- Quick checking of highway types
local types = {}
for _, k in ipairs(highway_types) do
    types[k] = 1
end

-- Parse a maxspeed to be number (in km/h)
local function parse_speed(input)
    if not input then
        return nil
    end

    local maxspeed = tonumber(input)
    if maxspeed then
        return maxspeed
    end

    if input:sub(-3) == 'mph' then
        local num = tonumber(input:sub(1, -4))
        if num then
            return math.floor(num * 1.60934)
        end
    end

    return nil
end

function osm2pgsql.process_node(object)
    -- if clean_tags(object.tags) then
    --     return
    -- end
    clean_tags(object.tags)

    if not object.tags.highway then
        return
    end

    tables.nodes:insert({
        geom = object:as_point(),
        type = object:grab_tag('highway'),
        tags = object.tags,
    })
end

function osm2pgsql.process_way(object)
    if clean_tags(object.tags) then
        return
    end

    if not object.tags.highway then
        return
    end

    local highway_type = object:grab_tag('highway')

    local name = object:grab_tag('name')
    
    local row = {
        name = name,
        type = highway_type,
        maxspeed = parse_speed(object.tags.maxspeed),
        oneway = object.tags.oneway or 0,
        lit = object.tags.lit,
        nodes = object.nodes,
        tags = object.tags,
        geom = object:as_linestring()
    }

    tables.ways:insert(row)

end

-- Process every relation in the input
function osm2pgsql.process_relation(object)
    if clean_tags(object.tags) then
        return
    end

    if not object.tags.highway then
        return
    end

    local highway_type = object:grab_tag('highway')

    tables.relations:insert({
        tags = object.tags,
        type = highway_type,
        members = object.members,
    })
end
