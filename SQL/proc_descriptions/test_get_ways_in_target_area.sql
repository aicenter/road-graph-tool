-- this file is purposed to to test function mentioned below
-- function: get_ways_in_target_area()

-- startup function
CREATE OR REPLACE FUNCTION startup_get_ways_in_target_area()
RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of startup_get_ways_in_target_area() started';
END;
$$ LANGUAGE plpgsql;

-- 1st case: no records on return, when there is no target_area
-- setup
CREATE OR REPLACE FUNCTION setup_get_ways_in_target_area_no_target_area()
RETURNS SETOF TEXT AS $$
BEGIN
    -- call startup
    RAISE NOTICE 'execution of setup_get_ways_in_target_area_no_target_area() started';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_get_ways_in_target_area_no_target_area()
RETURNS SETOF TEXT AS $$
BEGIN
    -- call setup
    RAISE NOTICE 'execution of test_get_ways_in_target_area_no_target_area() started';
--     RETURN QUERY SELECT * FROM get_ways_in_target_area(0);
    RETURN NEXT pass('no records on return, when there is no target_area');
END
$$ LANGUAGE plpgsql;

-- tests that shouldn't be executed in runtests('get_ways_in_target_area_no_target_area')

CREATE OR REPLACE FUNCTION startup_assign_average_speed_to_ways()
RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of startup_assign_average_speed_to_ways() started';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_assign_average_speed_to_ways()
RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'execution of setup_assign_average_speed_to_ways() started';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_assign_average_speed_to_ways()
RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'execution of test_assign_average_speed_to_ways() started';
    RETURN NEXT pass('PASSED test_assign_average_speed_to_ways');
END;
$$ LANGUAGE plpgsql;

-- DEBUG: running tests TODO remove
SELECT * FROM mob_group_runtests('_get_ways_in_target_area');
SELECT * FROM runtests();

DROP FUNCTION test_get_ways_in_target_area_no_target_area();
DROP FUNCTION test_assign_average_speed_to_ways();
