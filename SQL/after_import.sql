\echo 'Altering column nodes.id to integer...'

ALTER TABLE nodes ALTER COLUMN id TYPE integer;

\echo 'Altering column ways.id to integer...'

ALTER TABLE ways ALTER COLUMN id TYPE integer;

\echo 'Altering column relations.id to integer...'

ALTER TABLE relations ALTER COLUMN id TYPE integer;

\echo 'Altering column nodes_ways.id to integer...'

ALTER TABLE nodes_ways ALTER COLUMN way_id TYPE integer;

-- PRIMARY KEYS
\echo 'Adding PRIMARY KEY constraints to table nodes...'
ALTER TABLE nodes ADD CONSTRAINT pk_nodes PRIMARY KEY (id);

\echo 'Adding PRIMARY KEY constraints to table nodes_ways'
ALTER TABLE nodes_ways ADD CONSTRAINT nodes_ways_pk PRIMARY KEY (id);

\echo 'Adding PRIMARY KEY constraints to table ways...'
ALTER TABLE ways ADD CONSTRAINT pk_ways PRIMARY KEY (id);

\echo 'Adding PRIMARY KEY constraints to table relations...'
ALTER TABLE relations ADD CONSTRAINT pk_relations PRIMARY KEY (id);


-- FOREIGN KEYS
-- ways table foreign keys
\echo 'Adding FOREIGN KEY contraints to table ways...'

ALTER TABLE ways ADD CONSTRAINT fk_ways_from FOREIGN KEY ("from") REFERENCES nodes(id);
ALTER TABLE ways ADD CONSTRAINT fk_ways_to FOREIGN KEY ("to") REFERENCES nodes(id);
ALTER TABLE ways ADD CONSTRAINT fk_ways_area FOREIGN KEY (area) REFERENCES areas(id);

-- nodes table foreign key
\echo 'Adding FOREIGN KEY contraints to table nodes...'

ALTER TABLE nodes ADD CONSTRAINT fk_nodes_area FOREIGN KEY (area) REFERENCES areas(id);

-- edges table foreign keys
\echo 'Adding FOREIGN KEY contraints to table edges...'

ALTER TABLE edges ADD CONSTRAINT fk_edges_from FOREIGN KEY ("from") REFERENCES nodes(id);
ALTER TABLE edges ADD CONSTRAINT fk_edges_to FOREIGN KEY ("to") REFERENCES nodes(id);

-- trip_locations table foreign keys
\echo 'Adding FOREIGN KEY contraints to table trip_location...'

ALTER TABLE trip_locations ADD CONSTRAINT fk_trip_locations_destination FOREIGN KEY (destination) REFERENCES nodes(id);
ALTER TABLE trip_locations ADD CONSTRAINT fk_trip_locations_origin FOREIGN KEY (origin) REFERENCES nodes(id);

-- nodes_ways table foreign key
\echo 'Adding FOREIGN KEY contraints to table nodes_ways...'

ALTER TABLE nodes_ways ADD CONSTRAINT fk_nodes_ways_area FOREIGN KEY (area) REFERENCES areas(id);

-- nodes_ways_speeds table foreign keys
\echo 'Adding FOREIGN KEY contraints to table nodes_ways_speeds...'

ALTER TABLE nodes_ways_speeds ADD CONSTRAINT fk_nodes_ways_speeds_from FOREIGN KEY (from_node_ways_id) REFERENCES nodes_ways(id);
ALTER TABLE nodes_ways_speeds ADD CONSTRAINT fk_nodes_ways_speeds_to FOREIGN KEY (to_node_ways_id) REFERENCES nodes_ways(id);
