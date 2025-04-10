-- function: get_ways_in_target_area()
-- Renamed startup function to avoid pgtap auto-execution
CREATE OR REPLACE FUNCTION prepare_get_ways_test_area_1652() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of prepare_get_ways_test_area_1652() started';
    -- add area
    INSERT INTO areas(id, name, description, geom)
    VALUES (1652, 'test_area', 'description of test_area ', ST_GeomFromText('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))', 4326));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prepare_test_area_with_non_intersecting_ways() RETURNS VOID AS $$
BEGIN
    PERFORM prepare_get_ways_test_area_1652(); -- Ensure the area exists first
    RAISE NOTICE 'Preparing test area with non-intersecting ways';
    -- add nodes with id 1 and 2
    INSERT INTO nodes(id, area, geom) VALUES
    (1, 1652, ST_GeomFromText('POINT(0.5 0.5)', 4326)),
    (2, 1652, ST_GeomFromText('POINT(1 1)', 4326));

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

    -- Check that the function raises an exception when the requested area does not exist
    RETURN NEXT throws_ok(
        'SELECT * FROM get_ways_in_target_area(52::smallint)',
        'The target area with id 52 does not exist',
        'Function raises exception when requested area does not exist'
    );

    -- Clean up (optional, depending on test isolation needs)
    DELETE FROM areas WHERE id = 51;
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
    PERFORM prepare_get_ways_test_area_1652(); -- Ensure the area exists first
    RAISE NOTICE 'execution of setup_get_ways_in_target_area_ways_intersecting_target_area() started';
    -- add nodes with id 1 and 2
    INSERT INTO nodes(id, area, geom) VALUES
    (1, 1652, ST_GeomFromText('POINT(0.5 0.5)', 4326)),
    (2, 1652, ST_GeomFromText('POINT(1 1)', 4326));

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

-- 5th case: test loading road segments from GraphML
CREATE OR REPLACE FUNCTION prepare_test_area_with_graphml_ways() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Preparing test area with GraphML ways';
    -- Create the test area first
    INSERT INTO areas(id, name, description, geom)
    VALUES (9999, 'graphml_test_area', 'Test area for GraphML data', 
            ST_Buffer(ST_SetSRID(ST_MakePoint(0, 0), 4326), 0.001));  -- small buffer around [0,0]
    
    -- Load the test_1 graph into the database
    PERFORM load_graphml_to_nodes_edges('test_1');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_get_ways_in_target_area_graphml_ways() RETURNS SETOF TEXT AS $$
DECLARE
    way_count integer;
    selected_count integer;
BEGIN
    RAISE NOTICE '--- test_get_ways_in_target_area_graphml_ways ---';
    RAISE NOTICE 'Search path: %', current_setting('search_path');
    
    -- Setup test data
    PERFORM prepare_test_area_with_graphml_ways();

    -- Get the count of ways loaded from GraphML
    SELECT COUNT(*) INTO way_count FROM ways WHERE area = 9999;
    
    -- Verify that ways were created
    IF way_count = 0 THEN
        RETURN NEXT fail('No ways were created from GraphML data');
    ELSE
        RETURN NEXT pass(format('Successfully created %s ways from GraphML data', way_count));
    END IF;

    -- Verify that the ways have correct geometry
    IF EXISTS (
        SELECT 1 FROM ways 
        WHERE area = 9999 
        AND geom IS NULL
    ) THEN
        RETURN NEXT fail('Some ways have NULL geometry');
    ELSE
        RETURN NEXT pass('All ways have valid geometry');
    END IF;

    -- Verify that the ways have correct from/to nodes
    IF EXISTS (
        SELECT 1 FROM ways w
        WHERE area = 9999 
        AND (
            NOT EXISTS (SELECT 1 FROM nodes WHERE id = w."from" AND area = 9999)
            OR NOT EXISTS (SELECT 1 FROM nodes WHERE id = w."to" AND area = 9999)
        )
    ) THEN
        RETURN NEXT fail('Some ways reference non-existent nodes');
    ELSE
        RETURN NEXT pass('All ways reference valid nodes');
    END IF;

    -- Verify that get_ways_in_target_area selects all ways
    SELECT COUNT(*) INTO selected_count FROM get_ways_in_target_area(9999::smallint);
    
    IF selected_count != way_count THEN
        RETURN NEXT fail(format('get_ways_in_target_area returned %s ways, expected %s', selected_count, way_count));
    ELSE
        RETURN NEXT pass(format('get_ways_in_target_area correctly selected all %s ways', way_count));
    END IF;

    -- Clean up
    DELETE FROM ways WHERE area = 9999;
    DELETE FROM nodes WHERE area = 9999;
END;
$$ LANGUAGE plpgsql;
