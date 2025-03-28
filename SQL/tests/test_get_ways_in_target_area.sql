-- this file is purposed to to test function mentioned below

-- test delete area
CREATE OR REPLACE FUNCTION startup_delete_area() RETURNS VOID AS $$
BEGIN
    PERFORM startup_get_ways_in_target_area(); -- add area 'test_area'
    RAISE NOTICE 'execution of startup_delete_area() started';
    DELETE FROM ways WHERE area = 1652;
    DELETE FROM nodes WHERE area = 1652;
    DELETE FROM areas WHERE name = 'test_area';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_delete_area() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'execution of test_delete_area() started';
    -- check that there is no area named 'test_area'
    IF EXISTS (SELECT * FROM areas WHERE name = 'test_area') THEN
        RETURN NEXT fail('area test_area was not deleted');
    ELSE
        RETURN NEXT pass('area test_area was deleted');
    END IF;
END;
$$ LANGUAGE plpgsql;

-- function: get_ways_in_target_area()
-- setup function
CREATE OR REPLACE FUNCTION startup_get_ways_in_target_area() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of startup_get_ways_in_target_area() started';
    -- add area
    INSERT INTO areas(id, name, description, geom)
    VALUES (1652, 'test_area', 'description of test_area ', ST_GeomFromText('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))', 4326));

    -- add nodes with id 1 and 2
    INSERT INTO nodes(id, area, geom) VALUES
    (1, 1652, ST_GeomFromText('POINT(0.5 0.5)', 4326)),
    (2, 1652, ST_GeomFromText('POINT(1 1)', 4326));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prepare_test_area_with_non_intersecting_ways() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Preparing test area with non-intersecting ways';
    -- add ways, which do not intersect with the area
    INSERT INTO ways(id, tags, geom, area, "from", "to", oneway) VALUES
    (1, 'tiger:zip_left => 08330', ST_GeomFromText('LINESTRING(2 2, 2 3)', 4326), 1652, 1, 2, false),
    (2, 'tiger:zip_left => 08330', ST_GeomFromText('LINESTRING(2 3, 4 5)', 4326), 1652, 1, 2, false),
    (3, 'tiger:zip_left => 08330', ST_GeomFromText('LINESTRING(4 5, 4 6)', 4326), 1652, 1, 2, false);
END;
$$ LANGUAGE plpgsql;

-- 1st case: no records on return, when there is no target_area
CREATE OR REPLACE FUNCTION prepare_test_area_no_target_area() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of setup_get_ways_in_target_area_no_target_area() started';
    INSERT INTO areas(id, name, description, geom)
    VALUES (51, 'target area', 'target area', ST_GeomFromText('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))', 4326));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_get_ways_in_target_area_no_target_area() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'execution of test_get_ways_in_target_area_no_target_area() started';
    
    -- Setup test data
    PERFORM prepare_test_area_no_target_area();

    -- check that there is no area named 'test_area'
    IF EXISTS (SELECT * FROM areas WHERE id = 52) THEN
        RETURN NEXT fail('area test_area was not deleted');
    ELSE
        RETURN NEXT pass('area test_area was deleted');
    END IF;

    -- check that function returns no records when requested area does not exist
    IF EXISTS (SELECT * FROM get_ways_in_target_area(52::smallint)) THEN
        RETURN NEXT fail('function get_ways_in_target_area() returned records when requested area does not exist');
    ELSE
        RETURN NEXT pass('function get_ways_in_target_area() returned no records when requested area does not exist');
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 2nd case: no records on return, when there is no ways intersecting target_area
CREATE OR REPLACE FUNCTION test_get_ways_in_target_area_no_ways_intersecting_target_area() RETURNS SETOF TEXT AS $$
DECLARE
    items RECORD;
BEGIN
    RAISE NOTICE 'execution of test_get_ways_in_target_area_no_ways_intersecting_target_area() started';
    
    -- Setup test data
    PERFORM prepare_test_area_with_non_intersecting_ways();

    -- check that function returns no records when there are no ways intersecting target area
    IF EXISTS (SELECT * FROM get_ways_in_target_area(1652::smallint)) THEN
        RAISE NOTICE 'Intersecting ways found';
        FOR items IN SELECT * FROM get_ways_in_target_area(1652::smallint) LOOP
            RAISE NOTICE 'Selected way: id1: %, geom: %', items.id, items.geom;
        END LOOP;
        RETURN NEXT fail('function get_ways_in_target_area() returned records when there are no ways intersecting target area');
    ELSE
        RETURN NEXT pass('function get_ways_in_target_area() returned no records when there are no ways intersecting target area');
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 3rd case: records on return, when there are ways intersecting target_area
CREATE OR REPLACE FUNCTION prepare_test_area_with_intersecting_ways() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of setup_get_ways_in_target_area_ways_intersecting_target_area() started';
    -- add ways, which intersect with the area
    INSERT INTO ways(id, tags, geom, area, "from", "to", oneway) VALUES
    (4, 'tiger:zip_left => 08330', ST_GeomFromText('LINESTRING(0.5 0.5, 1 1)', 4326), 1652, 1, 2, false),
    (5, 'tiger:zip_left => 08330', ST_GeomFromText('LINESTRING(0.5 0.5, 0.5 1)', 4326), 1652, 1, 2, false),
    (6, 'tiger:zip_left => 08330', ST_GeomFromText('LINESTRING(0.5 0.5, 0 0)', 4326), 1652, 1, 2, false);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_get_ways_in_target_area_ways_intersecting_target_area() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'execution of test_get_ways_in_target_area_ways_intersecting_target_area() started';
    
    -- Setup test data
    PERFORM prepare_test_area_with_intersecting_ways();

    RETURN NEXT set_eq('SELECT * FROM get_ways_in_target_area(1652::smallint)', 'SELECT * FROM ways WHERE id IN (4, 5, 6)',
        'function get_ways_in_target_area() returned correct records');
END
$$ LANGUAGE plpgsql;

-- 4th case: exception when target area has NULL geometry
CREATE OR REPLACE FUNCTION prepare_test_area_with_null_geometry() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Preparing test area with NULL geometry';
    -- add area with NULL geometry
    INSERT INTO areas(id, name, description, geom)
    VALUES (1653, 'null_geom_area', 'area with NULL geometry', NULL);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_get_ways_in_target_area_null_geometry() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE '--- test_get_ways_in_target_area_null_geometry ---';
    
    -- Setup test data
    PERFORM prepare_test_area_with_null_geometry();

    -- Verify that the function raises an exception
    RETURN NEXT throws_ok(
        'SELECT * FROM get_ways_in_target_area(1653::smallint)',
        'The target area with id 1653 has a NULL geometry',
        'Function raises exception when target area has NULL geometry'
    );
END;
$$ LANGUAGE plpgsql;

-- tests that shouldn't be executed in any mob_group_runtests() as they are not mentioned in any mob_group_runtests() call
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

-- Example of running tests
-- Note: for now as we do not have automatic grouping of tests, we need to run tests with as much precise group naming as possible !!!
-- SELECT * FROM mob_group_runtests('_get_ways_in_target_area$'); -- runs only startup
-- SELECT * FROM mob_group_runtests('_get_ways_in_target_area'); -- runs only startup
-- SELECT * FROM mob_group_runtests('_delete_area'); -- WARNING: startup_delete_area calls startup_get_ways_in_target_area, corresponding text will be printed
-- SELECT * FROM mob_group_runtests('public', '_get_ways_in_target_area_no_target_area'); -- tests 1st case
-- SELECT * FROM mob_group_runtests('_get_ways_in_target_area_no_ways_intersecting_target_area'); -- tests 2nd case
-- SELECT * FROM mob_group_runtests('_get_ways_in_target_area_ways_intersecting_target_area'); -- tests 3rd case

-- Example of combination
CREATE OR REPLACE FUNCTION run_all_get_ways_in_target_area_tests() RETURNS SETOF TEXT AS
$$
BEGIN
    -- run tests
    RETURN QUERY SELECT * FROM mob_group_runtests('_get_ways_in_target_area$')
    UNION ALL
    SELECT * FROM mob_group_runtests('_get_ways_in_target_area')
    UNION ALL
    SELECT * FROM mob_group_runtests('_delete_area')
    UNION ALL
    SELECT * FROM mob_group_runtests('public', '_get_ways_in_target_area_no_target_area')
    UNION ALL
    SELECT * FROM mob_group_runtests('_get_ways_in_target_area_no_ways_intersecting_target_area')
    UNION ALL
    SELECT * FROM mob_group_runtests('_get_ways_in_target_area_ways_intersecting_target_area')
    UNION ALL
    SELECT * FROM mob_group_runtests('_get_ways_in_target_area_null_geometry');
END;
$$ LANGUAGE plpgsql;

-- DROP FUNCTION IF EXISTS run_all_tests();
-- SELECT * FROM run_all_tests();
