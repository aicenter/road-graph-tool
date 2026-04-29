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
-- Name: ways_tmp pk_ways_tmp; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways_tmp
    ADD CONSTRAINT pk_ways_tmp PRIMARY KEY (id);
