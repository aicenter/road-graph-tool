--
-- Name: nodes; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS {schema}.nodes (
    id bigint NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    area integer,
    contracted boolean DEFAULT false NOT NULL
);


--
-- Name: COLUMN nodes.area; Type: COMMENT; Schema: public
--

COMMENT ON COLUMN {schema}.nodes.area IS 'Area with which was the node imported to the database';


--
-- Name: nodes pk_nodes; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY {schema}.nodes
    ADD CONSTRAINT pk_nodes PRIMARY KEY (id);


--
-- Name: nodes_area_index; Type: INDEX; Schema: public
--

CREATE INDEX nodes_area_index ON {schema}.nodes USING btree (area);


--
-- Name: nodes_geom_index; Type: INDEX; Schema: public
--

-- CREATE INDEX nodes_geom_index ON {schema}.nodes USING gist (geom);


--
-- Name: nodes fk_nodes_areas_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY {schema}.nodes
    ADD CONSTRAINT fk_nodes_areas_1 FOREIGN KEY (area) REFERENCES {schema}.areas(id);
