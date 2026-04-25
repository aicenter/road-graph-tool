--
-- Name: speed_records_quarterly; Type: TABLE; Schema: public
--

CREATE TABLE IF NOT EXISTS public.speed_records_quarterly (
    year smallint,
    quarter smallint,
    hour smallint,
    from_osm_id bigint,
    to_osm_id bigint,
    speed_mean double precision,
    st_dev double precision,
    speed_p50 double precision,
    speed_p85 double precision,
    dataset smallint
);
