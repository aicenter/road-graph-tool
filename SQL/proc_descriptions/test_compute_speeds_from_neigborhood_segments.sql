-- Procedure: compute_speeds_from_neigborhood_segments()
-- Testing cases:
-- 1. **Invalid data**. Either passed value Is NULL -> test for throwing an error. (`target_area_id` is used only in creation __VIEW__ `target_ways`)
-- 2. **Invalid data**. Given input is valid, but some data are missing from used tables (`areas`, `nodes`, `nodes_ways`) -> no new entries to target table. Basically check that no errors are raised.
-- 3. **Standard case**. All values present both in args and tables -> check that average is as expected by every quality in range[3,5].
-- 4. **Standard case**. Second execution of the procedure with the same args does not lead to creation of duplicates.
-- Table dependency tree:
-- `areas` <- `ways` <- `nodes` <- `nodes_ways` <- `nodes_ways_speeds`.

-- DEBUG: TODO remove
-- CALL test_env_constructor();
-- startup function for all tests
CREATE OR REPLACE FUNCTION startup_compute_speeds_from_neighborhood_segments()
RETURNS VOID AS $$
    BEGIN
        -- insert area
        INSERT INTO areas (id, name, geom) VALUES (1, 'Test area', ST_GeomFromText('POLYGON((-100 -300, -100 100, 100 100, 100 -300, -100 -300))', 4326));

        -- insert nodes
        INSERT INTO nodes (id, geom, area) VALUES (1, ST_GeomFromText('POINT(1 1)', 4326), 1);
--                                                   (2, ST_GeomFromText('POINT(1 2)', 4326), 1),
--                                                   (3, ST_GeomFromText('POINT(3 3)', 4326), 1),
--                                                   (4, ST_GeomFromText('POINT(2 1)', 4326), 1),
--                                                   (5, ST_GeomFromText('POINT(4 2)', 4326), 1);
        INSERT INTO nodes (id, geom, area) VALUES (6, ST_GeomFromText('POINT(20 -5)', 4326), 1),
                                                  (7, ST_GeomFromText('POINT(50 -5)', 4326), 1),
                                                  (8, ST_GeomFromText('POINT(100 -5)', 4326), 1),
                                                  (9, ST_GeomFromText('POINT(-20 5)', 4326), 1),
                                                  (10, ST_GeomFromText('POINT(-50 5)', 4326), 1),
                                                  (11, ST_GeomFromText('POINT(-100 5)', 4326), 1),
                                                  (12, ST_GeomFromText('POINT(-100 -250)', 4326), 1),
                                                  (13, ST_GeomFromText('POINT(100 -250)', 4326), 1);

        -- insert ways
        INSERT INTO ways (id, tags, geom, area, "from", "to", oneway) VALUES
--             (1, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 1, 1 2)', 4326), 1, 1, 2, false),
--             (2, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 1, 2 1)', 4326), 1, 1, 4, false),
-- --             (3, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 2, 3 3)', 4326), 1, 2, 3, true),
--             (4, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(2 1, 4 2)', 4326), 1, 4, 5, false),
--             (5, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(3 3, 4 2)', 4326), 1, 3, 5, false),
            (6, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 1, 20 -5, 50 -5, 100 -5)', 4326), 1, 1, 8, false),
            (7, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 1, -20 5, -50 5, -100 5)', 4326), 1, 1, 11, false),
            (8, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(-100 -250, 100 -250)', 4326), 1, 12, 13, false);

        -- insert nodes_ways
--         INSERT INTO nodes_ways (way_id, node_id, position, area, id) VALUES
--             (1, 2, 1, 1, 1),
--             (1, 1, 2, 1, 2),
--             (2, 1, 1, 1, 3),
--             (2, 4, 2, 1, 4),
--             (4, 4, 1, 1, 5),
--             (4, 5, 2, 1, 6),
--             (5, 3, 1, 1, 7),
--             (5, 5, 2, 1, 8);
        INSERT INTO nodes_ways (way_id, node_id, position, area, id) VALUES
            (6, 1, 1, 1, 9),
            (6, 6, 2, 1, 10),
            (6, 7, 3, 1, 11),
            (6, 8, 4, 1, 12),
            (7, 1, 1, 1, 13),
            (7, 9, 2, 1, 14),
            (7, 10, 3, 1, 15),
            (7, 11, 4, 1, 16),
            (8, 12, 1, 1, 17),
            (8, 13, 2, 1, 18);


        -- insert nodes_ways_speeds
--         INSERT INTO nodes_ways_speeds (from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
--             (1, 10, 1, 2, 1, 1),
--             (3, 20, 1, 4, 1, 1),
--             (5, 30, 1, 6, 1, 1),
--             (7, 40, 1, 8, 1, 1);
        INSERT INTO nodes_ways_speeds (from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
            (9, 50, 1, 10, 1, 1),
            (10, 80, 1, 11, 1, 1),
            (11, 50, 1, 12, 1, 1),
            (13, 50, 1, 14, 1, 1);
--             (14, 80, 1, 15, 1, 1),
--             (15, 50, 1, 16, 1, 1);
    END;
$$ LANGUAGE plpgsql;

-- DEBUG: TODO remove
-- SELECT * FROM startup_compute_speeds_from_neighborhood_segments();
-- SELECT * FROM test_compute_speeds_from_neigborhood_segments_3();
-- SELECT * FROM test_env.nodes_ways_speeds WHERE quality != 1 ORDER BY from_node_ways_id, to_node_ways_id;
-- SELECT * FROM setup_compute_speeds_from_neighborhood_segments_2();
-- CALL test_env_destructor();

-- 1st case: Invalid data. `target_area_id` is NULL OR `target_area_srid` is NULL
CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_1() RETURNS SETOF TEXT AS $$
    BEGIN
    RETURN NEXT diag('Checking that an error is thrown when `target_area_id` is NULL');
    RETURN NEXT throws_ok('compute_speeds_from_neighborhood_segments(NULL::smallint, 4326::integer)');

    RETURN NEXT diag('Checking that an error is thrown when `target_area_srid` is NULL');
    RETURN NEXT throws_ok('compute_speeds_from_neighborhood_segments(1::smallint, NULL::integer)');
    END;
$$ LANGUAGE plpgsql;

-- 2nd case: Invalid data. Given input is valid, but some data are missing from used tables

CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2() RETURNS SETOF TEXT AS $$
    BEGIN
        -- save all nodes_ways_speeds
        CREATE TABLE test2_expected_results AS
        SELECT * FROM nodes_ways_speeds;
    END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_areas() RETURNS SETOF TEXT AS $$
    BEGIN
        Delete from areas;
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_areas() RETURNS SETOF TEXT AS $$
    BEGIN
    CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
    RETURN NEXT diag('"areas" was cleared. Expecting no new entries to be added');
    RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_nodes() RETURNS SETOF TEXT AS $$
    BEGIN
        Delete from nodes;
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_nodes() RETURNS SETOF TEXT AS $$
    BEGIN
    CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
    RETURN NEXT diag('"nodes" was cleared. Expecting no new entries to be added');
    RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_nodesways() RETURNS SETOF TEXT AS $$
    BEGIN
        Delete from nodes_ways;
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_nodesways() RETURNS SETOF TEXT AS $$
    BEGIN
    CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
    RETURN NEXT diag('"nodes_ways" was cleared. Expecting no new entries to be added');
    RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
    END;
$$ LANGUAGE plpgsql;

-- 3rd case: Standard case. All values present both in args and tables

CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_3() RETURNS SETOF TEXT AS $$
    BEGIN
        CREATE TEMP TABLE test3_expected_results AS
        SELECT *
        FROM (
            VALUES (10, 60, 1, 9, 3, 3),
                   (11, 60, 1, 10, 3, 3),
                   (12, 65, 1, 11, 3, 2),
                   (14, 50, 1, 13, 3, 2),
                   (14, 50, 1, 15, 3, 1),
                   (15, 50, 1, 14, 3, 1),
                   (15, 57.5, 1, 16, 4, 4),
                   (16, 57.5, 1, 15, 4, 4),
                   (17, 57.5, 1, 18, 5, 4),
                   (18, 57.5, 1, 17, 5, 4)
             );
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_3() RETURNS SETOF TEXT AS $$
    BEGIN
    CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
    RETURN NEXT diag('Checking that computed results are as expected');
    RETURN NEXT set_eq('SELECT * FROM test3_expected_results', 'SELECT * FROM nodes_ways_speeds WHERE quality IN (3,4,5)');
    END;
$$ LANGUAGE plpgsql;

-- 4th case: Standard case. Second execution of the procedure with the same args does not lead to creation of duplicates
CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_4() RETURNS SETOF TEXT AS $$
    DECLARE
        record RECORD;
    BEGIN
        FOR record IN
            SELECT * FROM setup_compute_speeds_from_neighborhood_segments_3()
        LOOP
            RETURN NEXT record;
        END LOOP;

        ALTER TABLE test3_expected_results RENAME TO test4_expected_results;
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_4() RETURNS SETOF TEXT AS $$
    BEGIN
    CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
    RETURN NEXT diag('Checking that computed results are as expected');
    RETURN NEXT set_eq('SELECT * FROM test4_expected_results', 'SELECT * FROM nodes_ways_speeds WHERE quality IN (3,4,5)');

    -- now executing once more
    CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
    RETURN NEXT diag('Checking that no new records were added');
    RETURN NEXT set_eq('SELECT * FROM test4_expected_results', 'SELECT * FROM nodes_ways_speeds WHERE quality IN (3,4,5)');
    END;
$$ LANGUAGE plpgsql;

-- all tests
CREATE OR REPLACE FUNCTION run_all_compute_speeds_from_neighborhood_segments() RETURNS SETOF TEXT AS $$
    DECLARE
        record RECORD;
BEGIN
    FOR record IN
        SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_1')
        UNION ALL
        SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_areas')
        UNION ALL
        SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_nodes')
        UNION ALL
        SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_nodesways')
        UNION ALL
        SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_3')
        UNION ALL
        SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_4')
    LOOP
        RETURN NEXT record;
    END LOOP;

END;
$$ LANGUAGE plpgsql;

-- Run function
-- SELECT * FROM run_all_compute_speeds_from_neighborhood_segments();