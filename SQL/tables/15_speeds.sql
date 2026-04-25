--
-- Name: speeds; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speeds (
    way_id bigint NOT NULL,
    speed_dataset smallint NOT NULL,
    speed real NOT NULL,
    way_area integer NOT NULL,
    speed_source smallint NOT NULL
);


--
-- Name: speeds speeds_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.speeds
    ADD CONSTRAINT speeds_pkey PRIMARY KEY (way_id, way_area, speed_dataset);


--
-- Name: speeds fk_speeds_speed_datasets_1; Type: FK CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.speeds
    ADD CONSTRAINT fk_speeds_speed_datasets_1 FOREIGN KEY (speed_dataset) REFERENCES public.speed_datasets(id);
