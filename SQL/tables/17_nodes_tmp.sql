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
-- Name: nodes_tmp id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.nodes_tmp ALTER COLUMN id SET DEFAULT nextval('public.nodes_tmp_seq'::regclass);


--
-- Name: nodes_tmp pk_nodes_tmp; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_tmp
    ADD CONSTRAINT pk_nodes_tmp PRIMARY KEY (id);


--
-- Name: nodes_tmp_osm_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_tmp_osm_id_index ON public.nodes_tmp USING btree (osm_id);
