--
-- Name: nodes_tags; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.nodes_tags (
    node_id bigint NOT NULL,
    tag_id integer NOT NULL,
    tag_value text NOT NULL
);


--
-- Name: nodes_tags pk_nodes_tags; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_tags
    ADD CONSTRAINT pk_nodes_tags PRIMARY KEY (node_id, tag_id);


--
-- Name: nodes_tags_tag_id_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_tags_tag_id_index ON public.nodes_tags USING btree (tag_id);

CREATE INDEX nodes_tags_node_id_index ON public.nodes_tags USING btree (node_id);


--
-- Name: nodes_tags nodes_tags_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_tags
    ADD CONSTRAINT nodes_tags_nodes_id_fk FOREIGN KEY (node_id) REFERENCES public.nodes(id) ON DELETE CASCADE;


--
-- Name: nodes_tags nodes_tags_tags_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.nodes_tags
    ADD CONSTRAINT nodes_tags_tags_id_fk FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE;
