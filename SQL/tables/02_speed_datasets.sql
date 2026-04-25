--
-- Name: speed_datasets; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_datasets (
    id integer NOT NULL,
    name character varying NOT NULL,
    description character varying
);


--
-- Name: speed_datasets speed_datasets_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.speed_datasets
    ADD CONSTRAINT speed_datasets_pkey PRIMARY KEY (id);
