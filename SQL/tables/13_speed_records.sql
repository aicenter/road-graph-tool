--
-- Name: speed_records; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_records (
    datetime timestamp without time zone NOT NULL,
    from_osm_id bigint NOT NULL,
    to_osm_id bigint NOT NULL,
    speed real NOT NULL,
    st_dev real,
    dataset smallint
);


--
-- Name: speed_records_from_osm_id_to_osm_id_index; Type: INDEX; Schema: public
--

CREATE INDEX speed_records_from_osm_id_to_osm_id_index ON public.speed_records USING btree (from_osm_id, to_osm_id);
