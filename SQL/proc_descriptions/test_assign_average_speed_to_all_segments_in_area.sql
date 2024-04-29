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

-- begin named transaction
BEGIN TRANSACTION;
CALL test_env_constructor();
SELECT * FROM startup_aastas();
CALL test_env_destructor();
END TRANSACTION;
SELECT * FROM areas;
SHOW SEARCH_PATH;

-- startup function for aastas
CREATE OR REPLACE FUNCTION startup_aastas() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Executing startup for assign_average_speed_to_all_segments_in_area';
    RAISE NOTICE 'Inserting into areas';
    -- insert one area
    INSERT INTO areas (id, name, description, geom) VALUES (1, 'Test Area', 'Test Area Description', ST_GeomFromText('POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))', 4326));

    RAISE NOTICE 'Inserting into nodes';
    -- insert 5 nodes within the test area
    INSERT INTO nodes(id, geom, area, contracted) VALUES (1, ST_GeomFromText('POINT(1 1)', 4326), 1, false)
    , (2, ST_GeomFromText('POINT(1 5)', 4326), 1, false)
    , (3, ST_GeomFromText('POINT(5 5)', 4326), 1, false)
    , (4, ST_GeomFromText('POINT(5 1)', 4326), 1, false)
    , (5, ST_GeomFromText('POINT(9 1)', 4326), 1, false);
    -- insert 3 nodes outside the test area
    INSERT INTO nodes(id, geom, area, contracted) VALUES (6, ST_GeomFromText('POINT(11 1)', 4326), 1, false),
    (7, ST_GeomFromText('POINT(11 5)', 4326), 1, false),
    (8, ST_GeomFromText('POINT(11 11)', 4326), 1, false);

    -- insert 2 ways within the test area
    RAISE NOTICE 'Inserting into ways';
    INSERT INTO ways(id, tags, geom, area, "from", "to", oneway) VALUES (1, '{example_tag => example}', ST_GeomFromText('LINESTRING(1 1, 1 5, 5 5)', 4326), 1, 1, 3, false),
    (2, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(5 5, 5 1, 9 1)', 4326), 1, 3, 5, false);

    -- insert 1 way outside the test area
    INSERT INTO ways(id, tags, geom, area, "from", "to", oneway) VALUES (3, '{example_tag => example_3}', ST_GeomFromText('LINESTRING(11 1, 11 5, 11 11)', 4326), 1, 6, 8, false);

    -- insert 1 way with a segment outside the test area
    INSERT INTO ways(id, tags, geom, area, "from", "to", oneway) VALUES (4, '{example_tag => example_4}', ST_GeomFromText('LINESTRING(1 1, 1 5, 11 5)', 4326), 1, 1, 7, false);

    -- insert nodes_ways
    RAISE NOTICE 'Inserting into nodes_ways';
    INSERT INTO nodes_ways(way_id, node_id, position, area, id) VALUES -- create nodes_ways for every node in the way
    (1, 1, 1, 1, 1), (1, 2, 2, 1, 2), (1, 3, 3, 1, 3),
    (2, 3, 1, 1, 4), (2, 4, 2, 1, 5), (2, 5, 3, 1, 6),
    (3, 6, 1, 1, 7), (3, 7, 2, 1, 8), (3, 8, 3, 1, 9),
    (4, 1, 1, 1, 10), (4, 2, 2, 1, 11), (4, 7, 3, 1, 12);

    -- create temporary table for expected output
    CREATE TEMP TABLE expected_nodes_ways_speeds AS
    SELECT * FROM nodes_ways_speeds WITH NO DATA;
END;
$$ LANGUAGE plpgsql;

-- test case 1: testing both segments with matching speeds
CREATE OR REPLACE FUNCTION setup_aastas_output_1() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Executing setup for test_aastas_output_1';
    RAISE NOTICE 'Case: matching speeds';
    -- insert 2 nodes_ways_speeds
    RAISE NOTICE 'Inserting into nodes_ways_speeds';
    INSERT INTO nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                        (1, 70, 0, 1, 2, 1),
                                                                                                                        (2, 70, 0, 2, 2, 1);

    -- inserting expected output
    WITH source_records_count AS (
        SELECT
            COUNT(*) AS count
        FROM
            nodes_ways_speeds
    )
    INSERT INTO expected_nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                                 (1, 70, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 70, 0, 1, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (2, 70, 0, 3, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (3, 70, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (4, 70, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (5, 70, 0, 4, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (5, 70, 0, 6, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (6, 70, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (10, 70, 0, 11, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (11, 70, 0, 10, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (11, 70, 0, 12, 5, (SELECT count FROM source_records_count)),
                                                                                                                                    (12, 70, 0, 11, 5, (SELECT count FROM source_records_count));


END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_aastas_output() RETURNS SETOF TEXT AS $$
    BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output';
    RAISE NOTICE 'Checking that the get_ways_in_target_area function returns non-empty result';

    RETURN NEXT diag('Checking that the get_ways_in_target_area function returns non-empty result');
    RETURN NEXT isnt_empty('SELECT * FROM get_ways_in_target_area(1::smallint)');

    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_aastas_output_1() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output_1';

    CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1);

    -- check that there are some records in the nodes_ways_speeds table with quality 5 - meaning assertion,
    --  that some records were added
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with quality equal to 5');
    RETURN NEXT isnt_empty('SELECT * FROM nodes_ways_speeds WHERE quality = 5');

    -- check that the nodes_ways_speeds table has been updated
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with average speed equal to 70 and quality equal to 5');
    RETURN NEXT set_eq('SELECT * FROM expected_nodes_ways_speeds', 'SELECT * FROM nodes_ways_speeds WHERE quality = 5');
END;
$$ LANGUAGE plpgsql;

-- test case 2: testing both segments with non-matching speeds
CREATE OR REPLACE FUNCTION setup_aastas_output_2() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Executing setup for test_aastas_output_2';
    RAISE NOTICE 'Case: non-matching speeds';
    -- insert 2 nodes_ways_speeds
    RAISE NOTICE 'Inserting into nodes_ways_speeds';
    INSERT INTO nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                        (1, 70, 0, 1, 2, 1),
                                                                                                                        (2, 75, 0, 2, 2, 1),
                                                                                                                        (3, 80, 0, 4, 1, 1);

    -- inserting expected output
    WITH source_records_count AS (
        SELECT
            COUNT(*) AS count
        FROM
            nodes_ways_speeds
    )
    INSERT INTO expected_nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                                 (1, 75, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 75, 0, 1, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 75, 0, 3, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (3, 75, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (4, 75, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (5, 75, 0, 4, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (5, 75, 0, 6, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (6, 75, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (10, 75, 0, 11, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (11, 75, 0, 10, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (11, 75, 0, 12, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (12, 75, 0, 11, 5, (SELECT count FROM source_records_count));

END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_aastas_output_2() RETURNS SETOF TEXT AS $$
BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output_2';

    CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1);

    -- check that there are some records in the nodes_ways_speeds table with quality 5 - meaning assertion,
    --  that some records were added
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with quality equal to 5');
    RETURN NEXT isnt_empty('SELECT * FROM nodes_ways_speeds WHERE quality = 5');

    -- check that the nodes_ways_speeds table has been updated
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with average speed equal to 70 and quality equal to 5');
    RETURN NEXT set_eq('SELECT * FROM expected_nodes_ways_speeds', 'SELECT * FROM nodes_ways_speeds WHERE quality = 5');
end;
$$ LANGUAGE plpgsql;

-- test case 3: segments with matching speeds in oneway
CREATE OR REPLACE FUNCTION setup_aastas_output_3() RETURNS VOID AS $$
    BEGIN
    RAISE NOTICE 'Executing setup for test_aastas_output_3';
    RAISE NOTICE 'Case: matching speeds in oneway';

    -- update all ways to be oneway
    UPDATE ways SET oneway = true WHERE TRUE;

    -- insert 2 nodes_ways_speeds
    RAISE NOTICE 'Inserting into nodes_ways_speeds';
    INSERT INTO nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                        (1, 70, 0, 1, 2, 1),
                                                                                                                        (2, 70, 0, 2, 2, 1);

    -- inserting expected output
    WITH source_records_count AS (
        SELECT
            COUNT(*) AS count
        FROM
            nodes_ways_speeds
    )
    INSERT INTO expected_nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                                 (1, 70, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 70, 0, 3, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (4, 70, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (5, 70, 0, 6, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (10, 70, 0, 11, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (11, 70, 0, 12, 5, (SELECT count FROM source_records_count));
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_aastas_output_3() RETURNS SETOF TEXT AS $$
    BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output_3';

    CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1);

    -- check that there are some records in the nodes_ways_speeds table with quality 5 - meaning assertion,
    --  that some records were added
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with quality equal to 5');
    RETURN NEXT isnt_empty('SELECT * FROM nodes_ways_speeds WHERE quality = 5');

    -- check that the nodes_ways_speeds table has been updated
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with average speed equal to 70 and quality equal to 5');
    RETURN NEXT set_eq('SELECT * FROM expected_nodes_ways_speeds', 'SELECT * FROM nodes_ways_speeds WHERE quality = 5');
    END;
$$ LANGUAGE plpgsql;

-- test case 4: segments without matching speeds in oneway
CREATE OR REPLACE FUNCTION setup_aastas_output_4() RETURNS VOID AS $$
    BEGIN
    RAISE NOTICE 'Executing setup for test_aastas_output_4';
    RAISE NOTICE 'Case: non-matching speeds in oneway';

    -- update all ways to be oneway
    UPDATE ways SET oneway = true WHERE TRUE;

    -- insert 3 nodes_ways_speeds
    RAISE NOTICE 'Inserting into nodes_ways_speeds';
    INSERT INTO nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                        (1, 70, 0, 1, 2, 1),
                                                                                                                        (2, 75, 0, 2, 2, 1),
                                                                                                                        (3, 80, 0, 4, 1, 1);

    -- inserting expected output
    WITH source_records_count AS (
        SELECT
            COUNT(*) AS count
        FROM
            nodes_ways_speeds
    )
    INSERT INTO expected_nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                                 (1, 75, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 75, 0, 3, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (4, 75, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (5, 75, 0, 6, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (10, 75, 0, 11, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (11, 75, 0, 12, 5, (SELECT count FROM source_records_count));
    END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_aastas_output_4() RETURNS SETOF TEXT AS $$
    BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output_4';

    CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1);

    -- check that there are some records in the nodes_ways_speeds table with quality 5 - meaning assertion,
    --  that some records were added
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with quality equal to 5');
    RETURN NEXT isnt_empty('SELECT * FROM nodes_ways_speeds WHERE quality = 5');

    -- check that the nodes_ways_speeds table has been updated
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with average speed equal to 70 and quality equal to 5');
    RETURN NEXT set_eq('SELECT * FROM expected_nodes_ways_speeds', 'SELECT * FROM nodes_ways_speeds WHERE quality = 5');
    END;
$$ LANGUAGE plpgsql;

-- case 5: double execution of the procedure leads to the same result as one execution
CREATE OR REPLACE FUNCTION setup_aastas_double_exec() RETURNS VOID AS $$
    BEGIN
    RAISE NOTICE 'Executing setup for test_aastas_output_double_exec';
    RAISE NOTICE 'Case: double execution';

    -- insert 2 nodes_ways_speeds
    RAISE NOTICE 'Inserting into nodes_ways_speeds';
    INSERT INTO nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                        (1, 70, 0, 1, 2, 1),
                                                                                                                        (2, 70, 0, 2, 2, 1);

    -- inserting expected output
    WITH source_records_count AS (
        SELECT
            COUNT(*) AS count
        FROM
            nodes_ways_speeds
    )
    INSERT INTO expected_nodes_ways_speeds(from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
                                                                                                                                 (1, 70, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 70, 0, 1, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (2, 70, 0, 3, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (3, 70, 0, 2, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (4, 70, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (5, 70, 0, 4, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (5, 70, 0, 6, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (6, 70, 0, 5, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (10, 70, 0, 11, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (11, 70, 0, 10, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (11, 70, 0, 12, 5, (SELECT count FROM source_records_count)),
                                                                                                                                 (12, 70, 0, 11, 5, (SELECT count FROM source_records_count));
    END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_aastas_double_exec() RETURNS SETOF TEXT AS $$
    BEGIN
    RAISE NOTICE 'Executing test for test_aastas_output_double_exec';

    CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1);
    CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1);

    -- check that there are some records in the nodes_ways_speeds table with quality 5 - meaning assertion,
    --  that some records were added
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with quality equal to 5');
    RETURN NEXT isnt_empty('SELECT * FROM nodes_ways_speeds WHERE quality = 5');

    -- check that the nodes_ways_speeds table has been updated
    RETURN NEXT diag('Checking that the nodes_ways_speeds table has been updated and contains records with average speed equal to 70 and quality equal to 5');
    RETURN NEXT set_eq('SELECT * FROM expected_nodes_ways_speeds', 'SELECT * FROM nodes_ways_speeds WHERE quality = 5');
    END;
$$ LANGUAGE plpgsql;

-- case 6: calling procedure with invalid area id leads to an error
CREATE OR REPLACE FUNCTION test_aastas_invalid_area_id() RETURNS SETOF TEXT AS $$
    BEGIN
    RAISE NOTICE 'Executing test for test_aastas_invalid_area_id';

    -- check that the procedure throws an error when called with an invalid area id
    RETURN NEXT diag('Checking that the procedure throws an error when called with an invalid area id');
    RETURN NEXT throws_ok('CALL assign_average_speed_to_all_segments_in_area(2::smallint, 1)', '22023'); -- invalid_parameter_value

    END;
$$ LANGUAGE plpgsql;

-- case 7: no records in nodes_ways_speeds leads to an error
CREATE OR REPLACE FUNCTION test_aastas_no_records() RETURNS SETOF TEXT AS $$
    BEGIN
    RAISE NOTICE 'Executing test for test_aastas_no_records';

    -- check that the procedure throws an error when called with an invalid area id
    RETURN NEXT diag('Checking that the procedure throws an error when there are no records in nodes_ways_speeds');
    RETURN NEXT throws_ok('CALL assign_average_speed_to_all_segments_in_area(1::smallint, 1)', '22023'); -- invalid_parameter_value

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
        UNION ALL
        SELECT * FROM mob_group_runtests('_aastas_output_3')
        UNION ALL
        SELECT * FROM mob_group_runtests('_aastas_output_4')
        UNION ALL
        SELECT * FROM mob_group_runtests('_aastas_double_exec')
        UNION ALL
        SELECT * FROM mob_group_runtests('_aastas_invalid_area_id')
        UNION ALL
        SELECT * FROM mob_group_runtests('_aastas_no_records')
    LOOP
        RETURN NEXT record;
    END loop;
END;
$$ LANGUAGE plpgsql;

-- DEBUG: TODO delete
SELECT * FROM run_all_aastas_tests();