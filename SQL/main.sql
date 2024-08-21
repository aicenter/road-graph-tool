--
-- Reduced PostgreSQL database dump (functions and procedures are in separate files)
--

-- Dumped from database version 12.12 (Debian 12.12-1.pgdg100+1)
-- Dumped by pg_dump version 12.12 (Debian 12.12-1.pgdg100+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: hstore; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS hstore WITH SCHEMA public;


--
-- Name: EXTENSION hstore; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION hstore IS 'data type for storing sets of (key, value) pairs';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: pgrouting; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgrouting WITH SCHEMA public;


--
-- Name: EXTENSION pgrouting; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgrouting IS 'pgRouting Extension';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: address_block; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.address_block (
    id integer NOT NULL,
    name character varying,
    centroid public.geometry(Point,4326) NOT NULL
);


--
-- Name: areas; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.areas (
    id integer NOT NULL,
    name character varying NOT NULL,
    description character varying,
    geom public.geometry(MultiPolygon)
);


--
-- Name: component_data; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.component_data (
    component_id smallint NOT NULL,
    node_id bigint NOT NULL,
    area smallint NOT NULL
);


--
-- Name: COLUMN component_data.component_id; Type: COMMENT; Schema: public
--

COMMENT ON COLUMN public.component_data.component_id IS 'ID of the component, ordered from the largests components, starting from 0';


--
-- Name: COLUMN component_data.area; Type: COMMENT; Schema: public
--

COMMENT ON COLUMN public.component_data.area IS 'The area for which this component record belongs. Note that one node can be part of the largest component in one area while a part of a small one in some other area ';


--
-- Name: dataset_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.dataset_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: dataset; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.dataset (
    id integer DEFAULT nextval('public.dataset_id_seq'::regclass) NOT NULL,
    name character varying,
    description character varying,
    area integer
);


--
-- Name: demand; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.demand (
    id integer NOT NULL,
    origin bigint NOT NULL,
    destination bigint NOT NULL,
    origin_time timestamp without time zone NOT NULL,
    dataset integer NOT NULL,
    passenger_count smallint DEFAULT 1,
    destination_time timestamp without time zone,
    source_id bigint
);


--
-- Name: nodes; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes (
    id bigint NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    area integer,
    contracted boolean DEFAULT false NOT NULL
);


--
-- Name: COLUMN nodes.area; Type: COMMENT; Schema: public
--

COMMENT ON COLUMN public.nodes.area IS 'Area with which was the node imported to the database';


--
-- Name: trip_locations; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.trip_locations (
    request_id integer NOT NULL,
    origin bigint NOT NULL,
    destination bigint NOT NULL,
    set integer NOT NULL
);


--
-- Name: dc_demand; Type: VIEW; Schema: public
--

CREATE OR REPLACE VIEW public.dc_demand AS
 SELECT demand.id,
    origin_nodes.geom AS origin,
    destination_nodes.geom AS destination,
    demand.origin_time,
    demand.destination_time
   FROM (((public.demand
     JOIN public.trip_locations ON ((demand.id = trip_locations.request_id)))
     JOIN public.nodes origin_nodes ON ((trip_locations.origin = origin_nodes.id)))
     JOIN public.nodes destination_nodes ON ((trip_locations.destination = destination_nodes.id)))
  WHERE (demand.dataset = 7);


--
-- Name: demand_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.demand_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: edges; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.edges (
    "from" bigint,
    "to" bigint,
    id integer NOT NULL,
    geom public.geometry(MultiLineString) NOT NULL,
    area smallint NOT NULL,
    speed double precision NOT NULL
);


--
-- Name: COLUMN edges.area; Type: COMMENT; Schema: public
--

COMMENT ON COLUMN public.edges.area IS 'The are for which the edge was generated using the simplification/contraction procedure';


--
-- Name: edge_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.edge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nodes_ways; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes_ways (
    way_id integer NOT NULL,
    node_id bigint NOT NULL,
    "position" smallint NOT NULL,
    area smallint,
    id integer NOT NULL
);


--
-- Name: nodes_ways_speeds; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes_ways_speeds (
    from_node_ways_id integer NOT NULL,
    speed double precision NOT NULL,
    st_dev double precision NOT NULL,
    to_node_ways_id integer NOT NULL,
    quality smallint,
    source_records_count integer
);


--
-- Name: node_segment_data; Type: VIEW; Schema: public
--

CREATE OR REPLACE VIEW public.node_segment_data AS
 SELECT row_number() OVER () AS id,
    public.st_makeline(from_nodes.geom, to_nodes.geom) AS geom,
    nodes_ways_speeds.speed,
    nodes_ways_speeds.quality
   FROM ((((public.nodes_ways_speeds
     JOIN public.nodes_ways from_nodes_ways ON ((nodes_ways_speeds.from_node_ways_id = from_nodes_ways.id)))
     JOIN public.nodes_ways to_nodes_ways ON ((nodes_ways_speeds.to_node_ways_id = to_nodes_ways.id)))
     JOIN public.nodes from_nodes ON ((from_nodes_ways.node_id = from_nodes.id)))
     JOIN public.nodes to_nodes ON ((to_nodes_ways.node_id = to_nodes.id)));


--
-- Name: nodes_edges; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes_edges (
    node_id integer NOT NULL,
    edge_id integer NOT NULL
);


--
-- Name: nodes_tmp; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes_tmp (
    id integer NOT NULL,
    geom public.geometry(Point,4326),
    osm_id bigint
);


--
-- Name: nodes_tmp_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.nodes_tmp_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nodes_ways_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.nodes_ways_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nodes_ways_tmp; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes_ways_tmp (
    way_id integer NOT NULL,
    node_id integer NOT NULL,
    "position" smallint NOT NULL
);

--
-- Name: positions_view; Type: VIEW; Schema: public
--

CREATE OR REPLACE VIEW public.positions_view AS
 SELECT trip_locations.request_id,
    trip_locations.set,
    origin_nodes.geom AS origin,
    destination_nodes.geom AS destination
   FROM ((public.trip_locations
     JOIN public.nodes origin_nodes ON ((trip_locations.origin = origin_nodes.id)))
     JOIN public.nodes destination_nodes ON ((trip_locations.destination = destination_nodes.id)));


--
-- Name: relation_members; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.relation_members (
    relation_id bigint NOT NULL,
    member_id integer NOT NULL,
    member_type text NOT NULL,
    member_role text NOT NULL,
    sequence_id integer NOT NULL
);
ALTER TABLE ONLY public.relation_members ALTER COLUMN relation_id SET (n_distinct=-0.09);
ALTER TABLE ONLY public.relation_members ALTER COLUMN member_id SET (n_distinct=-0.62);
ALTER TABLE ONLY public.relation_members ALTER COLUMN member_role SET (n_distinct=6500);
ALTER TABLE ONLY public.relation_members ALTER COLUMN sequence_id SET (n_distinct=10000);


--
-- Name: relations; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.relations (
    id bigint NOT NULL,
    tags public.hstore,
    members jsonb
);


--
-- Name: schema_info; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.schema_info (
    version integer NOT NULL
);


--
-- Name: speed_datasets; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_datasets (
    id integer NOT NULL,
    name character varying NOT NULL,
    description character varying
);


--
-- Name: speed_record_datasets; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_record_datasets (
    id smallint,
    name character varying,
    description character varying
);


--
-- Name: speed_records; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_records (
    datetime timestamp without time zone NOT NULL,
    from_osm_id bigint NOT NULL,
    to_osm_id bigint NOT NULL,
    speed real NOT NULL,
    st_dev real,
    dataset smallint
);


--
-- Name: speed_records_quarterly; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_records_quarterly (
    year smallint,
    quarter smallint,
    hour smallint,
    from_osm_id bigint,
    to_osm_id bigint,
    speed_mean double precision,
    st_dev double precision,
    speed_p50 double precision,
    speed_p85 double precision,
    dataset smallint
);


--
-- Name: speeds; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speeds (
    way_id bigint NOT NULL,
    speed_dataset smallint NOT NULL,
    speed real NOT NULL,
    way_area integer NOT NULL,
    speed_source smallint NOT NULL
);


--
-- Name: trip_location_sets; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.trip_location_sets (
    id integer NOT NULL,
    description character varying NOT NULL
);


--
-- Name: trip_location_sets_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.trip_location_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trip_time_sets; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.trip_time_sets (
    id integer NOT NULL,
    description character varying
);


--
-- Name: trip_time_sets_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.trip_time_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trip_times; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.trip_times (
    request_id integer NOT NULL,
    "time" timestamp without time zone NOT NULL,
    set integer NOT NULL
);


--
-- Name: ways; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.ways (
    id bigint NOT NULL,
    tags public.hstore,
    geom public.geometry(Geometry,4326) NOT NULL,
    area integer,
    "from" bigint NOT NULL,
    "to" bigint NOT NULL,
    oneway boolean NOT NULL
);


--
-- Name: ways_tmp; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.ways_tmp (
    id bigint NOT NULL,
    tags public.hstore,
    geom public.geometry(Geometry,4326) NOT NULL,
    "from" integer NOT NULL,
    "to" integer NOT NULL,
    osm_id bigint NOT NULL,
    oneway boolean NOT NULL
);


--
-- Name: zone_type; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.zone_type (
    id smallint NOT NULL,
    name character varying NOT NULL
);


--
-- Name: zone level_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public."zone level_id_seq"
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zones; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.zones (
    id bigint NOT NULL,
    name character varying,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    type smallint NOT NULL
);


--
-- Name: areas id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.areas ALTER COLUMN id SET DEFAULT nextval('public.dataset_id_seq'::regclass);


--
-- Name: demand id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.demand ALTER COLUMN id SET DEFAULT nextval('public.demand_id_seq'::regclass);


--
-- Name: edges id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.edges ALTER COLUMN id SET DEFAULT nextval('public.edge_id_seq'::regclass);


--
-- Name: nodes_tmp id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.nodes_tmp ALTER COLUMN id SET DEFAULT nextval('public.nodes_tmp_seq'::regclass);


--
-- Name: nodes_ways id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways ALTER COLUMN id SET DEFAULT nextval('public.nodes_ways_id_seq'::regclass);


--
-- Name: trip_location_sets id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.trip_location_sets ALTER COLUMN id SET DEFAULT nextval('public.trip_location_sets_id_seq'::regclass);


--
-- Name: trip_time_sets id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.trip_time_sets ALTER COLUMN id SET DEFAULT nextval('public.trip_time_sets_id_seq'::regclass);


--
-- Name: zone_type id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.zone_type ALTER COLUMN id SET DEFAULT nextval('public."zone level_id_seq"'::regclass);


--
-- Name: address_block address_block_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.address_block
    ADD CONSTRAINT address_block_pk PRIMARY KEY (id);


--
-- Name: component_data component_data_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.component_data
    ADD CONSTRAINT component_data_pk PRIMARY KEY (node_id, area);


--
-- Name: dataset dataset_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.dataset
    ADD CONSTRAINT dataset_pk PRIMARY KEY (id);


--
-- Name: areas dataset_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT dataset_pkey PRIMARY KEY (id);


--
-- Name: demand demand_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.demand
    ADD CONSTRAINT demand_pkey PRIMARY KEY (id);


--
-- Name: demand demand_source_key; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.demand
    ADD CONSTRAINT demand_source_key UNIQUE (source_id, dataset);


--
-- Name: edges edges_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.edges
    ADD CONSTRAINT edges_pk PRIMARY KEY (id);


--
-- Name: nodes_ways nodes_ways_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_pk PRIMARY KEY (id);


--
-- Name: nodes_ways_speeds nodes_ways_speed_records_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways_speeds
    ADD CONSTRAINT nodes_ways_speed_records_pk PRIMARY KEY (from_node_ways_id, to_node_ways_id);


--
-- Name: nodes_ways nodes_ways_unique_way_position; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_unique_way_position UNIQUE (way_id, "position");


--
-- Name: nodes pk_nodes; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT pk_nodes PRIMARY KEY (id);


--
-- Name: nodes_tmp pk_nodes_tmp; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_tmp
    ADD CONSTRAINT pk_nodes_tmp PRIMARY KEY (id);


--
-- Name: relation_members pk_relation_members; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.relation_members
    ADD CONSTRAINT pk_relation_members PRIMARY KEY (relation_id, sequence_id);


--
-- Name: relations pk_relations; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.relations
    ADD CONSTRAINT pk_relations PRIMARY KEY (id);


--
-- Name: schema_info pk_schema_info; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.schema_info
    ADD CONSTRAINT pk_schema_info PRIMARY KEY (version);


--
-- Name: ways pk_ways; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways
    ADD CONSTRAINT pk_ways PRIMARY KEY (id);


--
-- Name: ways_tmp pk_ways_tmp; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways_tmp
    ADD CONSTRAINT pk_ways_tmp PRIMARY KEY (id);


--
-- Name: speed_datasets speed_datasets_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.speed_datasets
    ADD CONSTRAINT speed_datasets_pkey PRIMARY KEY (id);


--
-- Name: speeds speeds_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.speeds
    ADD CONSTRAINT speeds_pkey PRIMARY KEY (way_id, way_area, speed_dataset);


--
-- Name: trip_location_sets trip_location_sets_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_location_sets
    ADD CONSTRAINT trip_location_sets_pkey PRIMARY KEY (id);


--
-- Name: trip_locations trip_locations_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_locations
    ADD CONSTRAINT trip_locations_pk PRIMARY KEY (request_id, set);


--
-- Name: trip_time_sets trip_time_sets_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_time_sets
    ADD CONSTRAINT trip_time_sets_pkey PRIMARY KEY (id);


--
-- Name: trip_times trip_times_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_times
    ADD CONSTRAINT trip_times_pk PRIMARY KEY (request_id, set);


--
-- Name: zone_type zone level_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.zone_type
    ADD CONSTRAINT "zone level_pk" PRIMARY KEY (id);


--
-- Name: zones zones_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_pk PRIMARY KEY (id, type);


--
-- Name: component_data_node_id_component_id_index; Type: INDEX; Schema: public
--

CREATE INDEX component_data_node_id_component_id_index ON public.component_data USING btree (node_id, component_id);


--
-- Name: component_data_node_id_index; Type: INDEX; Schema: public
--

CREATE INDEX component_data_node_id_index ON public.component_data USING btree (node_id);


--
-- Name: dataset__index; Type: INDEX; Schema: public
--

CREATE INDEX dataset__index ON public.demand USING btree (dataset);


--
-- Name: demand_dataset_destination_index; Type: INDEX; Schema: public
--

CREATE INDEX demand_dataset_destination_index ON public.demand USING btree (dataset, destination);


--
-- Name: demand_dataset_origin_index; Type: INDEX; Schema: public
--

CREATE INDEX demand_dataset_origin_index ON public.demand USING btree (dataset, origin);


--
-- Name: demand_destination_index; Type: INDEX; Schema: public
--

CREATE INDEX demand_destination_index ON public.demand USING btree (destination);


--
-- Name: demand_origin_index; Type: INDEX; Schema: public
--

CREATE INDEX demand_origin_index ON public.demand USING btree (origin);


--
-- Name: edges_from_index; Type: INDEX; Schema: public
--

CREATE INDEX edges_from_index ON public.edges USING btree ("from");


--
-- Name: edges_from_to_index; Type: INDEX; Schema: public
--

CREATE INDEX edges_from_to_index ON public.edges USING btree ("from", "to");


--
-- Name: edges_geom_index; Type: INDEX; Schema: public
--

CREATE INDEX edges_geom_index ON public.edges USING gist (geom);


--
-- Name: edges_to_index; Type: INDEX; Schema: public
--

CREATE INDEX edges_to_index ON public.edges USING btree ("to");


--
-- Name: geom__index; Type: INDEX; Schema: public
--

CREATE INDEX geom__index ON public.ways USING gist (geom);


--
-- Name: nodes_area_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_area_index ON public.nodes USING btree (area);


--
-- Name: nodes_geom_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_geom_index ON public.nodes USING gist (geom);


--
-- Name: nodes_tmp_osm_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_tmp_osm_id_index ON public.nodes_tmp USING btree (osm_id);


--
-- Name: nodes_ways_node_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_node_id_index ON public.nodes_ways USING btree (node_id);


--
-- Name: nodes_ways_speeds_from_node_ways_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_speeds_from_node_ways_id_index ON public.nodes_ways_speeds USING btree (from_node_ways_id);


--
-- Name: nodes_ways_speeds_to_node_ways_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_speeds_to_node_ways_id_index ON public.nodes_ways_speeds USING btree (to_node_ways_id);


--
-- Name: nodes_ways_way_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_way_id_index ON public.nodes_ways USING btree (way_id);


--
-- Name: origine_time__index; Type: INDEX; Schema: public
--

CREATE INDEX origine_time__index ON public.demand USING btree (origin_time);


--
-- Name: sidx_zones_geom; Type: INDEX; Schema: public
--

CREATE INDEX sidx_zones_geom ON public.zones USING gist (geom);


--
-- Name: speed_records_from_osm_id_to_osm_id_index; Type: INDEX; Schema: public
--

CREATE INDEX speed_records_from_osm_id_to_osm_id_index ON public.speed_records USING btree (from_osm_id, to_osm_id);


--
-- Name: trip_locations_destination_index; Type: INDEX; Schema: public
--

CREATE INDEX trip_locations_destination_index ON public.trip_locations USING btree (destination);


--
-- Name: trip_locations_origin_index; Type: INDEX; Schema: public
--

CREATE INDEX trip_locations_origin_index ON public.trip_locations USING btree (origin);


--
-- Name: ways_from_index; Type: INDEX; Schema: public
--

CREATE INDEX ways_from_index ON public.ways USING btree ("from");


--
-- Name: ways_to_index; Type: INDEX; Schema: public
--

CREATE INDEX ways_to_index ON public.ways USING btree ("to");


--
-- Name: zone level_id_uindex; Type: INDEX; Schema: public
--

CREATE UNIQUE INDEX "zone level_id_uindex" ON public.zone_type USING btree (id);


--
-- Name: component_data component_data_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.component_data
    ADD CONSTRAINT component_data_nodes_id_fk FOREIGN KEY (node_id) REFERENCES public.nodes(id);


--
-- Name: edges edges_areas_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.edges
    ADD CONSTRAINT edges_areas_id_fk FOREIGN KEY (area) REFERENCES public.areas(id);


--
-- Name: edges edges_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.edges
    ADD CONSTRAINT edges_nodes_id_fk FOREIGN KEY ("from") REFERENCES public.nodes(id);


--
-- Name: edges edges_nodes_id_fk2; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.edges
    ADD CONSTRAINT edges_nodes_id_fk2 FOREIGN KEY ("to") REFERENCES public.nodes(id);


--
-- Name: demand fk_demand_dataset_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.demand
    ADD CONSTRAINT fk_demand_dataset_1 FOREIGN KEY (dataset) REFERENCES public.dataset(id);


--
-- Name: nodes fk_nodes_areas_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT fk_nodes_areas_1 FOREIGN KEY (area) REFERENCES public.areas(id);


--
-- Name: speeds fk_speeds_speed_datasets_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.speeds
    ADD CONSTRAINT fk_speeds_speed_datasets_1 FOREIGN KEY (speed_dataset) REFERENCES public.speed_datasets(id);


--
-- Name: trip_locations fk_trip_locations_demand_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_locations
    ADD CONSTRAINT fk_trip_locations_demand_1 FOREIGN KEY (request_id) REFERENCES public.demand(id);


--
-- Name: trip_locations fk_trip_locations_trip_location_sets_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_locations
    ADD CONSTRAINT fk_trip_locations_trip_location_sets_1 FOREIGN KEY (set) REFERENCES public.trip_location_sets(id);


--
-- Name: trip_times fk_trip_times_demand_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_times
    ADD CONSTRAINT fk_trip_times_demand_1 FOREIGN KEY (request_id) REFERENCES public.demand(id);


--
-- Name: trip_times fk_trip_times_trip_time_sets_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_times
    ADD CONSTRAINT fk_trip_times_trip_time_sets_1 FOREIGN KEY (set) REFERENCES public.trip_time_sets(id);


--
-- Name: nodes_ways nodes_ways_areas_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_areas_id_fk FOREIGN KEY (area) REFERENCES public.areas(id);


--
-- Name: nodes_ways nodes_ways_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_nodes_id_fk FOREIGN KEY (node_id) REFERENCES public.nodes(id);


--
-- Name: nodes_ways_speeds nodes_ways_speeds_nodes_ways_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways_speeds
    ADD CONSTRAINT nodes_ways_speeds_nodes_ways_id_fk FOREIGN KEY (from_node_ways_id) REFERENCES public.nodes_ways(id);


--
-- Name: nodes_ways_speeds nodes_ways_speeds_nodes_ways_id_fk2; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways_speeds
    ADD CONSTRAINT nodes_ways_speeds_nodes_ways_id_fk2 FOREIGN KEY (to_node_ways_id) REFERENCES public.nodes_ways(id);


--
-- Name: nodes_ways nodes_ways_ways_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_ways_id_fk FOREIGN KEY (way_id) REFERENCES public.ways(id);


--
-- Name: trip_locations trip_locations_destination_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_locations
    ADD CONSTRAINT trip_locations_destination_nodes_id_fk FOREIGN KEY (destination) REFERENCES public.nodes(id);


--
-- Name: trip_locations trip_locations_origin_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.trip_locations
    ADD CONSTRAINT trip_locations_origin_nodes_id_fk FOREIGN KEY (origin) REFERENCES public.nodes(id);


--
-- Name: ways ways_areas_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways
    ADD CONSTRAINT ways_areas_id_fk FOREIGN KEY (area) REFERENCES public.areas(id);


--
-- Name: ways ways_from_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways
    ADD CONSTRAINT ways_from_nodes_id_fk FOREIGN KEY ("from") REFERENCES public.nodes(id);


--
-- Name: ways ways_to_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways
    ADD CONSTRAINT ways_to_nodes_id_fk FOREIGN KEY ("to") REFERENCES public.nodes(id);


--
-- Name: zones zones_type_fkey; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_type_fkey FOREIGN KEY (type) REFERENCES public.zone_type(id);


--
-- PostgreSQL database dump complete
--

