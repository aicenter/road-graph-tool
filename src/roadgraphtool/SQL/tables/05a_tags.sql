--
-- Name: tags; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS {schema}.tags (
    id integer NOT NULL,
    "key" text NOT NULL
);


--
-- Name: tags_id_seq; Type: SEQUENCE; Schema: public
--

CREATE SEQUENCE IF NOT EXISTS {schema}.tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tags id; Type: DEFAULT; Schema: public
--

ALTER TABLE ONLY {schema}.tags ALTER COLUMN id SET DEFAULT nextval('{schema}.tags_id_seq'::regclass);


--
-- Name: tags pk_tags; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY {schema}.tags
    ADD CONSTRAINT pk_tags PRIMARY KEY (id);


--
-- Name: tags tags_key_unique; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY {schema}.tags
    ADD CONSTRAINT tags_key_unique UNIQUE ("key");

CREATE INDEX tags_id_idx ON {schema}.tags USING btree ("id");
