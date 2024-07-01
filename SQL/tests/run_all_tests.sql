-- function to run all tests within road-graph-tool
CREATE OR REPLACE FUNCTION run_all_tests() RETURNS SETOF TEXT AS $$
    DECLARE
        record RECORD;
BEGIN
    RAISE NOTICE 'Running all tests...';
    FOR record IN
        SELECT * FROM run_all_aastas_tests()
        UNION ALL
        SELECT * FROM run_all_compute_speeds_from_neighborhood_segments_tests()
        UNION ALL
        SELECT * FROM run_all_get_ways_in_target_area_tests()
        -- TO BE ADDED manually
    LOOP
        RETURN NEXT record;
    END LOOP;
END;
$$ LANGUAGE plpgsql;