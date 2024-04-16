-- This file is purposed to test next procedure in the database
-- procedure name: assign_average_speed_to_all_segments_in_area
-- short name : aastas

-- startup function for aastas
CREATE OR REPLACE FUNCTION startup_aastas() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Executing startup for assign_average_speed_to_all_segments_in_area';
END;
$$ LANGUAGE plpgsql;

-- test case 1: testing both segments with matching speeds
CREATE OR REPLACE FUNCTION setup_aastas_output_1() RETURNS VOID AS $$
BEGIN
--     INSERT INTO segments (segment_id, area_id, speed) VALUES (1, 1, 10);
--     INSERT INTO segments (segment_id, area_id, speed) VALUES (2, 1, 10);
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_aastas_output_1() RETURNS SETOF TEXT AS $$
BEGIN
    RETURN QUERY SELECT * FROM pass('Debugging');

--     RETURN QUERY SELECT assign_average_speed_to_all_segments_in_area(1, 1);
END;
$$ LANGUAGE plpgsql;

-- DEBUG: TODO delete
-- SELECT * FROM mob_group_runtests('test_aastas_output_1');