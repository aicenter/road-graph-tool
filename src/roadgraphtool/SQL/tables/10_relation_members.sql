--
-- Name: relation_members; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.relation_members (
    relation_id bigint NOT NULL,
    member_id integer NOT NULL,
    member_type text NOT NULL,
    member_role text NOT NULL,
    sequence_id integer NOT NULL
);
ALTER TABLE ONLY public.relation_members ALTER COLUMN relation_id SET (n_distinct=-0.09);
ALTER TABLE ONLY public.relation_members ALTER COLUMN member_id SET (n_distinct=-0.62);
ALTER TABLE ONLY public.relation_members ALTER COLUMN member_role SET (n_distinct=6500);
ALTER TABLE ONLY public.relation_members ALTER COLUMN sequence_id SET (n_distinct=10000);


--
-- Name: relation_members pk_relation_members; Type: CONSTRAINT; Schema: public
--

ALTER TABLE ONLY public.relation_members
    ADD CONSTRAINT pk_relation_members PRIMARY KEY (relation_id, sequence_id);
