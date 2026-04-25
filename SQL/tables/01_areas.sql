--
-- Name: areas; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.areas (
    id integer NOT NULL,
    name character varying NOT NULL,
    description character varying,
    geom public.geometry(MultiPolygon)
);


--
-- Name: areas_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS public.areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: areas id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY public.areas ALTER COLUMN id SET DEFAULT nextval('public.areas_id_seq'::regclass);


--
-- Name: areas areas_pkey; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_pkey PRIMARY KEY (id);
