-- This file is purposed to test next procedure in the database
-- procedure name: assign_average_speed_to_all_segments_in_area
-- short name : aastas
-- test that after execution of this procedure,
-- some records were added to `nodes_ways_speeds` with corresponding values (which would be hardcoded to the assertion). Status: `approved`.
-- Note: multiple such tests needed,
-- 1) `testing both segments with matching speeds,
-- 2) without them
-- 3) and the combination of segments with
-- 4) and without matching speeds in one way`
-- Note: A segment is a line between two points in a way.


-- startup function for aastas
CREATE OR REPLACE FUNCTION startup_aastas() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Executing startup for assign_average_speed_to_all_segments_in_area';
END;
$$ LANGUAGE plpgsql;

-- test case 1: testing both segments with matching speeds
CREATE OR REPLACE FUNCTION setup_aastas_output_1() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Executing setup for test_aastas_output_1';
--     INSERT INTO segments (segment_id, area_id, speed) VALUES (1, 1, 10);
--     INSERT INTO segments (segment_id, area_id, speed) VALUES (2, 1, 10);
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_aastas_output_1() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output_1';

    RETURN QUERY SELECT * FROM pass('Debugging');

    CALL assign_average_speed_to_all_segments_in_area(1, 1);

--     RETURN QUERY SELECT assign_average_speed_to_all_segments_in_area(1, 1);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION run_all_aastas_tests() RETURNS SETOF TEXT AS $$
    DECLARE
        record RECORD;
BEGIN
    FOR record IN
        SELECT * FROM mob_group_runtests('_aastas_output_1')
        UNION ALL
        SELECT * FROM mob_group_runtests('_aastas_output_2')
        --- ADD MORE TESTS HERE
    LOOP
        RETURN NEXT record;
    END loop;
END;
$$ LANGUAGE plpgsql;

-- DEBUG: TODO delete
SELECT * FROM run_all_aastas_tests();