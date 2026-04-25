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

Column | Type | Description
------- | ------ | ------------
`id` | integer | Area identifier (default from `areas_id_seq`)
`name` | character varying | Area name
`description` | character varying | Optional description
`geom` | geometry(MultiPolygon) | Area geometry (SRID not enforced here)

# component_data

Column | Type | Description
------- | ------ | ------------
`component_id` | smallint | Component identifier (ordered from largest; starts at 0)
`node_id` | bigint | Node identifier (`nodes.id`)
`area` | smallint | Area id the component belongs to (`areas.id`)

# edges

Column | Type | Description
------- | ------ | ------------
`from` | bigint | Tail node id (`nodes.id`)
`to` | bigint | Head node id (`nodes.id`)
`id` | integer | Edge identifier (default from `edge_id_seq`)
`geom` | geometry(MultiLineString) | Edge geometry (WGS 84, 4326)
`area` | smallint | Area id the edge belongs to (`areas.id`)
`speed` | double precision | Edge speed (may be null / derived depending on pipeline stage)

# node_segment_data (view)

Columns exposed by the view (not a base table). Builds segments from `nodes_ways_speeds` by joining to `nodes_ways` and `nodes`.

Column | Type | Description
------- | ------ | ------------
`id` | bigint | Row number (generated)
`geom` | geometry | Line geometry between node points
`speed` | double precision | Speed assigned to the segment
`quality` | smallint | Quality indicator for the speed value

# nodes

Column | Type | Description
------- | ------ | ------------
`id` | bigint | Node identifier
`tags` | hstore | OSM-like tags key/value store
`geom` | geometry(Point, 4326) | Node geometry (WGS 84)
`area` | integer | Area id node was imported into (`areas.id`)
`contracted` | boolean | Whether node has been contracted (default `false`)

# nodes_edges

Column | Type | Description
------- | ------ | ------------
`node_id` | integer | Node identifier
`edge_id` | integer | Edge identifier

# nodes_tmp

Column | Type | Description
------- | ------ | ------------
`id` | integer | Temporary node identifier (default from `nodes_tmp_seq`)
`geom` | geometry(Point, 4326) | Node geometry (WGS 84)
`osm_id` | bigint | Original OSM id

# nodes_ways

Column | Type | Description
------- | ------ | ------------
`way_id` | integer | Way identifier (`ways.id`)
`node_id` | bigint | Node identifier (`nodes.id`)
`position` | smallint | Position of node in the way polyline
`area` | smallint | Area id (`areas.id`)
`id` | integer | Row identifier (default from `nodes_ways_id_seq`)

# nodes_ways_speeds

Column | Type | Description
------- | ------ | ------------
`from_node_ways_id` | integer | From endpoint in `nodes_ways.id`
`speed` | double precision | Speed estimate for the segment
`st_dev` | double precision | Standard deviation of speed estimate
`to_node_ways_id` | integer | To endpoint in `nodes_ways.id`
`quality` | smallint | Speed quality flag
`source_records_count` | integer | Number of source records used to compute speed (optional)

# nodes_ways_tmp

Column | Type | Description
------- | ------ | ------------
`way_id` | integer | Way identifier
`node_id` | integer | Node identifier
`position` | smallint | Position of node in the way polyline

# relation_members

Column | Type | Description
------- | ------ | ------------
`relation_id` | bigint | Relation identifier (`relations.id`)
`member_id` | integer | Member id (node/way/relation id depending on `member_type`)
`member_type` | text | Member type (e.g. node/way/relation)
`member_role` | text | Role string from OSM relation
`sequence_id` | integer | Position/order of the member within the relation

# relations

Column | Type | Description
------- | ------ | ------------
`id` | bigint | Relation identifier
`tags` | hstore | OSM-like tags key/value store
`members` | jsonb | Member list payload (if present)
`area` | int | Area id relation was imported into (`areas.id`)

# speed_datasets

Column | Type | Description
------- | ------ | ------------
`id` | integer | Speed dataset identifier
`name` | character varying | Dataset name
`description` | character varying | Dataset description

# speed_record_datasets

Column | Type | Description
------- | ------ | ------------
`id` | smallint | Speed-record dataset identifier
`name` | character varying | Dataset name
`description` | character varying | Dataset description

# speed_records

Column | Type | Description
------- | ------ | ------------
`datetime` | timestamp without time zone | Timestamp of record
`from_osm_id` | bigint | From OSM node id
`to_osm_id` | bigint | To OSM node id
`speed` | real | Speed value
`st_dev` | real | Standard deviation of speed value
`dataset` | smallint | Dataset id for the record

# speed_records_quarterly

Column | Type | Description
------- | ------ | ------------
`year` | smallint | Year
`quarter` | smallint | Quarter (1-4)
`hour` | smallint | Hour of day (0-23)
`from_osm_id` | bigint | From OSM node id
`to_osm_id` | bigint | To OSM node id
`speed_mean` | double precision | Mean speed
`st_dev` | double precision | Standard deviation
`speed_p50` | double precision | Median speed
`speed_p85` | double precision | 85th percentile speed
`dataset` | smallint | Dataset id for the record

# speeds

Column | Type | Description
------- | ------ | ------------
`way_id` | bigint | Way identifier (`ways.id`)
`speed_dataset` | smallint | Foreign key to `speed_datasets.id`
`speed` | real | Speed value
`way_area` | integer | Area id the way belongs to (`areas.id`)
`speed_source` | smallint | Indicates source/derivation of speed value

# ways

Column | Type | Description
------- | ------ | ------------
`id` | bigint | Way identifier
`tags` | hstore | OSM-like tags key/value store
`geom` | geometry(Geometry, 4326) | Way geometry (WGS 84)
`area` | integer | Area id the way belongs to (`areas.id`)
`from` | bigint | From node id (`nodes.id`)
`to` | bigint | To node id (`nodes.id`)
`oneway` | boolean | Directionality flag

# ways_tmp

Column | Type | Description
------- | ------ | ------------
`id` | bigint | Temporary way identifier
`tags` | hstore | OSM-like tags key/value store
`geom` | geometry(Geometry, 4326) | Way geometry (WGS 84)
`from` | integer | From node id (temporary / contracted pipeline stage)
`to` | integer | To node id (temporary / contracted pipeline stage)
`osm_id` | bigint | Original OSM way id
`oneway` | boolean | Directionality flag

