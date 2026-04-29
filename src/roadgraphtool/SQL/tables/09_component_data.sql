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
-- Name: component_data component_data_pk; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.component_data
    ADD CONSTRAINT component_data_pk PRIMARY KEY (node_id, area);


--
-- Name: component_data_node_id_component_id_index; Type: INDEX; Schema: public
--

CREATE INDEX component_data_node_id_component_id_index ON public.component_data USING btree (node_id, component_id);


--
-- Name: component_data_node_id_index; Type: INDEX; Schema: public
--

CREATE INDEX component_data_node_id_index ON public.component_data USING btree (node_id);


--
-- Name: component_data component_data_nodes_id_fk; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.component_data
    ADD CONSTRAINT component_data_nodes_id_fk FOREIGN KEY (node_id) REFERENCES public.nodes(id);
