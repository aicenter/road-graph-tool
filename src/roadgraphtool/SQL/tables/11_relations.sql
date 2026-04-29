--
-- Name: relations; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.relations (
    id bigint NOT NULL,
    tags public.hstore,
    members jsonb,
    area int
);


COMMENT ON COLUMN public.relations.area IS 'Area with which was the node imported to the database';


--
-- Name: relations pk_relations; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.relations
    ADD CONSTRAINT pk_relations PRIMARY KEY (id);


CREATE INDEX relations_area_index ON public.relations USING btree (area);


--
-- Name: relations fk_relations_areas_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.relations
    ADD CONSTRAINT fk_relations_areas_1 FOREIGN KEY (area) REFERENCES public.areas(id);
