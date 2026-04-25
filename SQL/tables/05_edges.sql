--
-- Name: edges; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.edges (
    "from" bigint,
    "to" bigint,
    id integer NOT NULL,
    geom public.geometry(MultiLineString) NOT NULL,
    area smallint NOT NULL,
    speed double precision 
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
-- Name: edges id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.edges ALTER COLUMN id SET DEFAULT nextval('public.edge_id_seq'::regclass);


--
-- Name: edges edges_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.edges
    ADD CONSTRAINT edges_pk PRIMARY KEY (id);


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
