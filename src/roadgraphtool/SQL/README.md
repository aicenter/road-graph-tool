Road Graph Tool SQL schema

Prerequisite: PostgreSQL with extensions enabled (see `schema_preamble.sql`):

- `postgis`
- `pgrouting`
- `hstore`

Apply in order:

1. `schema_preamble.sql`
2. `tables/*.sql` (lexicographic order)
3. `functions/*.sql`
4. `procedures/*.sql`

# areas

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | integer | Yes | Area identifier (default from `areas_id_seq`)
`name` | character varying | Yes | Area name
`description` | character varying | No | Optional description
`geom` | geometry(MultiPolygon) | No | Area geometry (SRID not enforced here)

# component_data

Column | Type | Required | Description
------- | ------ | ------ | ------------
`component_id` | smallint | Yes | Component identifier (ordered from largest; starts at 0)
`node_id` | bigint | Yes | Node identifier (`nodes.id`)
`area` | smallint | Yes | Area id the component belongs to (`areas.id`)

# edges

Column | Type | Required | Description
------- | ------ | ------ | ------------
`from` | bigint | No | Tail node id (`nodes.id`)
`to` | bigint | No | Head node id (`nodes.id`)
`id` | integer | Yes | Edge identifier (default from `edge_id_seq`)
`geom` | geometry(MultiLineString) | Yes | Edge geometry (WGS 84, 4326)
`area` | smallint | Yes | Area id the edge belongs to (`areas.id`)
`speed` | double precision | No | Edge speed (may be null / derived depending on pipeline stage)

# node_segment_data (view)

Columns exposed by the view (not a base table). Builds segments from `nodes_ways_speeds` by joining to `nodes_ways` and `nodes`.

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | bigint | Yes | Row number (generated)
`geom` | geometry | Yes | Line geometry between node points
`speed` | double precision | Yes | Speed assigned to the segment
`quality` | smallint | No | Quality indicator for the speed value

# nodes

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | bigint | Yes | Node identifier
`tags` | hstore | No | OSM-like tags key/value store
`geom` | geometry(Point, 4326) | Yes | Node geometry (WGS 84)
`area` | integer | No | Area id node was imported into (`areas.id`)
`contracted` | boolean | Yes | Whether node has been contracted (default `false`)

# nodes_edges

Column | Type | Required | Description
------- | ------ | ------ | ------------
`node_id` | integer | Yes | Node identifier
`edge_id` | integer | Yes | Edge identifier

# nodes_tmp

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | integer | Yes | Temporary node identifier (default from `nodes_tmp_seq`)
`geom` | geometry(Point, 4326) | No | Node geometry (WGS 84)
`osm_id` | bigint | No | Original OSM id

# nodes_ways

Column | Type | Required | Description
------- | ------ | ------ | ------------
`way_id` | integer | Yes | Way identifier (`ways.id`)
`node_id` | bigint | Yes | Node identifier (`nodes.id`)
`position` | smallint | Yes | Position of node in the way polyline
`area` | smallint | No | Area id (`areas.id`)
`id` | integer | Yes | Row identifier (default from `nodes_ways_id_seq`)

# nodes_ways_speeds

Column | Type | Required | Description
------- | ------ | ------ | ------------
`from_node_ways_id` | integer | Yes | From endpoint in `nodes_ways.id`
`speed` | double precision | Yes | Speed estimate for the segment
`st_dev` | double precision | Yes | Standard deviation of speed estimate
`to_node_ways_id` | integer | Yes | To endpoint in `nodes_ways.id`
`quality` | smallint | No | Speed quality flag
`source_records_count` | integer | No | Number of source records used to compute speed (optional)

# nodes_ways_tmp

Column | Type | Required | Description
------- | ------ | ------ | ------------
`way_id` | integer | Yes | Way identifier
`node_id` | integer | Yes | Node identifier
`position` | smallint | Yes | Position of node in the way polyline

# relation_members

Column | Type | Required | Description
------- | ------ | ------ | ------------
`relation_id` | bigint | Yes | Relation identifier (`relations.id`)
`member_id` | integer | Yes | Member id (node/way/relation id depending on `member_type`)
`member_type` | text | Yes | Member type (e.g. node/way/relation)
`member_role` | text | Yes | Role string from OSM relation
`sequence_id` | integer | Yes | Position/order of the member within the relation

# relations

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | bigint | Yes | Relation identifier
`tags` | hstore | No | OSM-like tags key/value store
`members` | jsonb | No | Member list payload (if present)
`area` | int | No | Area id relation was imported into (`areas.id`)

# speed_datasets

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | integer | Yes | Speed dataset identifier
`name` | character varying | Yes | Dataset name
`description` | character varying | No | Dataset description

# speed_record_datasets

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | smallint | No | Speed-record dataset identifier
`name` | character varying | No | Dataset name
`description` | character varying | No | Dataset description

# speed_records

Column | Type | Required | Description
------- | ------ | ------ | ------------
`datetime` | timestamp without time zone | Yes | Timestamp of record
`from_osm_id` | bigint | Yes | From OSM node id
`to_osm_id` | bigint | Yes | To OSM node id
`speed` | real | Yes | Speed value
`st_dev` | real | No | Standard deviation of speed value
`dataset` | smallint | No | Dataset id for the record

# speed_records_quarterly

Column | Type | Required | Description
------- | ------ | ------ | ------------
`year` | smallint | No | Year
`quarter` | smallint | No | Quarter (1-4)
`hour` | smallint | No | Hour of day (0-23)
`from_osm_id` | bigint | No | From OSM node id
`to_osm_id` | bigint | No | To OSM node id
`speed_mean` | double precision | No | Mean speed
`st_dev` | double precision | No | Standard deviation
`speed_p50` | double precision | No | Median speed
`speed_p85` | double precision | No | 85th percentile speed
`dataset` | smallint | No | Dataset id for the record

# speeds

Column | Type | Required | Description
------- | ------ | ------ | ------------
`way_id` | bigint | Yes | Way identifier (`ways.id`)
`speed_dataset` | smallint | Yes | Foreign key to `speed_datasets.id`
`speed` | real | Yes | Speed value
`way_area` | integer | Yes | Area id the way belongs to (`areas.id`)
`speed_source` | smallint | Yes | Indicates source/derivation of speed value

# ways

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | bigint | Yes | Way identifier
`tags` | hstore | No | OSM-like tags key/value store
`geom` | geometry(Geometry, 4326) | Yes | Way geometry (WGS 84)
`area` | integer | No | Area id the way belongs to (`areas.id`)
`from` | bigint | Yes | From node id (`nodes.id`)
`to` | bigint | Yes | To node id (`nodes.id`)
`oneway` | boolean | Yes | Directionality flag

# ways_tmp

Column | Type | Required | Description
------- | ------ | ------ | ------------
`id` | bigint | Yes | Temporary way identifier
`tags` | hstore | No | OSM-like tags key/value store
`geom` | geometry(Geometry, 4326) | Yes | Way geometry (WGS 84)
`from` | integer | Yes | From node id (temporary / contracted pipeline stage)
`to` | integer | Yes | To node id (temporary / contracted pipeline stage)
`osm_id` | bigint | Yes | Original OSM way id
`oneway` | boolean | Yes | Directionality flag

