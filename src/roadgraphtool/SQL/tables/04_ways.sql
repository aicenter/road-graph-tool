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
-- Name: ways pk_ways; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways
    ADD CONSTRAINT pk_ways PRIMARY KEY (id);


--
-- Name: geom__index; Type: INDEX; Schema: public
--

-- CREATE INDEX geom__index ON public.ways USING gist (geom);


--
-- Name: ways_from_index; Type: INDEX; Schema: public
--

CREATE INDEX ways_from_index ON public.ways USING btree ("from");


--
-- Name: ways_to_index; Type: INDEX; Schema: public
--

CREATE INDEX ways_to_index ON public.ways USING btree ("to");


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
