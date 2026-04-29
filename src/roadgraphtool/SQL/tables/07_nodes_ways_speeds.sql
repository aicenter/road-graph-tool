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
-- Name: nodes_ways_speeds nodes_ways_speed_records_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_ways_speeds
    ADD CONSTRAINT nodes_ways_speed_records_pk PRIMARY KEY (from_node_ways_id, to_node_ways_id);


--
-- Name: nodes_ways_speeds_from_node_ways_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_speeds_from_node_ways_id_index ON public.nodes_ways_speeds USING btree (from_node_ways_id);


--
-- Name: nodes_ways_speeds_to_node_ways_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_ways_speeds_to_node_ways_id_index ON public.nodes_ways_speeds USING btree (to_node_ways_id);


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
