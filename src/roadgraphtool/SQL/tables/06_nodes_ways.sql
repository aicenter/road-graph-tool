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
-- Name: nodes_ways id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways ALTER COLUMN id SET DEFAULT nextval('public.nodes_ways_id_seq'::regclass);


--
-- Name: nodes_ways nodes_ways_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_pk PRIMARY KEY (id);


--
-- Name: nodes_ways nodes_ways_unique_way_position; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_unique_way_position UNIQUE (way_id, "position");


--
-- Name: nodes_ways_node_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_node_id_index ON public.nodes_ways USING btree (node_id);


--
-- Name: nodes_ways_way_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_way_id_index ON public.nodes_ways USING btree (way_id);


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
-- Name: nodes_ways nodes_ways_ways_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways
    ADD CONSTRAINT nodes_ways_ways_id_fk FOREIGN KEY (way_id) REFERENCES public.ways(id);
