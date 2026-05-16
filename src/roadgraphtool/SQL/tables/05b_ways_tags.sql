--
-- Name: ways_tags; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.ways_tags (
    way_id bigint NOT NULL,
    tag_id integer NOT NULL,
    tag_value text NOT NULL
);


--
-- Name: ways_tags pk_ways_tags; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways_tags
    ADD CONSTRAINT pk_ways_tags PRIMARY KEY (way_id, tag_id);


--
-- Name: ways_tags_tag_id_index; Type: INDEX; Schema: public
--

CREATE INDEX ways_tags_tag_id_index ON public.ways_tags USING btree (tag_id);

CREATE INDEX ways_tags_way_id_index ON public.ways_tags USING btree (way_id);


--
-- Name: ways_tags ways_tags_tags_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways_tags
    ADD CONSTRAINT ways_tags_tags_id_fk FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE;


--
-- Name: ways_tags ways_tags_ways_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.ways_tags
    ADD CONSTRAINT ways_tags_ways_id_fk FOREIGN KEY (way_id) REFERENCES public.ways(id) ON DELETE CASCADE;
