--
-- Name: nodes; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes (
    id bigint NOT NULL,
    tags hstore,
    geom public.geometry(Point,4326) NOT NULL,
    area integer,
    contracted boolean DEFAULT false NOT NULL
);


--
-- Name: COLUMN nodes.area; Type: COMMENT; Schema: public
--

COMMENT ON COLUMN public.nodes.area IS 'Area with which was the node imported to the database';


--
-- Name: nodes pk_nodes; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT pk_nodes PRIMARY KEY (id);


--
-- Name: nodes_area_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_area_index ON public.nodes USING btree (area);


--
-- Name: nodes_geom_index; Type: INDEX; Schema: public
--

-- CREATE INDEX nodes_geom_index ON public.nodes USING gist (geom);


--
-- Name: nodes fk_nodes_areas_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT fk_nodes_areas_1 FOREIGN KEY (area) REFERENCES public.areas(id);
