-- Procedure: compute_speeds_from_neigborhood_segments()
-- Testing cases:
-- 1. **Invalid data**. Either passed value Is NULL -> test for throwing an error. (`target_area_id` is used only in creation __VIEW__ `target_ways`)
-- 2. **Invalid data**. Given input is valid, but some data are missing from used tables (`areas`, `nodes`, `nodes_ways`) -> no new entries to target table. Basically check that no errors are raised.
-- 3. **Standard case**. All values present both in args and tables -> check that average is as expected by every quality in range[3,5].
-- 4. **Standard case**. Second execution of the procedure with the same args does not lead to creation of duplicates.
-- Table dependency tree:
-- `areas` <- `ways` <- `nodes` <- `nodes_ways` <- `nodes_ways_speeds`.

-- startup function for all tests
CREATE OR REPLACE FUNCTION startup_compute_speeds_from_neighborhood_segments()
RETURNS VOID AS $$
	BEGIN
		RAISE NOTICE '--- startup_compute_speeds_from_neighborhood_segments ---';
		-- insert area
		INSERT INTO areas (id, name, geom) VALUES (1, 'Test area', ST_GeomFromText('POLYGON((-100 -300, -100 100, 100 100, 100 -300, -100 -300))', 4326));

		-- insert nodes
		INSERT INTO nodes (id, geom, area) VALUES (1, ST_GeomFromText('POINT(1 1)', 4326), 1);
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
			(6, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 1, 20 -5, 50 -5, 100 -5)', 4326), 1, 1, 8, false),
			(7, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(1 1, -20 5, -50 5, -100 5)', 4326), 1, 1, 11, false),
			(8, '{example_tag => example_2}', ST_GeomFromText('LINESTRING(-100 -250, 100 -250)', 4326), 1, 12, 13, false);

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

		INSERT INTO nodes_ways_speeds (from_node_ways_id, speed, st_dev, to_node_ways_id, quality, source_records_count) VALUES
			(9, 50, 1, 10, 1, 1),
			(10, 80, 1, 11, 1, 1),
			(11, 50, 1, 12, 1, 1),
			(13, 50, 1, 14, 1, 1);
	END;
$$ LANGUAGE plpgsql;


-- 1st case: Invalid data. `target_area_id` is NULL OR `target_area_srid` is NULL
CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_1() RETURNS SETOF TEXT AS $$
	BEGIN
	RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_1 ---';
	RETURN NEXT diag('Checking that an error is thrown when `target_area_id` is NULL');
	RETURN NEXT throws_ok('compute_speeds_from_neighborhood_segments(NULL::smallint, 4326::integer)');

	RETURN NEXT diag('Checking that an error is thrown when `target_area_srid` is NULL');
	RETURN NEXT throws_ok('compute_speeds_from_neighborhood_segments(1::smallint, NULL::integer)');
	END;
$$ LANGUAGE plpgsql;


-- 2nd case: Invalid data. Given input is valid, but some data are missing from used tables
CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_2 ---';
		-- save all nodes_ways_speeds
		CREATE TABLE test2_expected_results AS
		SELECT * FROM nodes_ways_speeds;
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_areas() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_2_areas ---';
		Delete from areas;
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_areas() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_2_areas ---';
	CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
	RETURN NEXT diag('"areas" was cleared. Expecting no new entries to be added');
	RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_nodes() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_2_nodes ---';
		Delete from nodes;
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_nodes() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_2_nodes ---';
	CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
	RETURN NEXT diag('"nodes" was cleared. Expecting no new entries to be added');
	RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_nodesways() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_2_nodesways ---';
		Delete from nodes_ways;
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_nodesways() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_2_nodesways ---';
	CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
	RETURN NEXT diag('"nodes_ways" was cleared. Expecting no new entries to be added');
	RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_2_ways() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_2_ways ---';
		Delete from ways;
	END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_compute_speeds_from_neighborhood_segments_2_ways() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_2_ways ---';
	CALL compute_speeds_from_neighborhood_segments(1::smallint, 4326::integer);
	RETURN NEXT diag('"ways" was cleared. Expecting no new entries to be added');
	RETURN NEXT set_eq('SELECT * FROM nodes_ways_speeds', 'SELECT * FROM test2_expected_results');
	END;
$$ LANGUAGE plpgsql;


-- 3rd case: Standard case. All values present both in args and tables
CREATE OR REPLACE FUNCTION setup_compute_speeds_from_neighborhood_segments_3() RETURNS SETOF TEXT AS $$
	BEGIN
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_3 ---';
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
		RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_3 ---';
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
		RAISE NOTICE '--- setup_compute_speeds_from_neighborhood_segments_4 ---';
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
		RAISE NOTICE '--- test_compute_speeds_from_neighborhood_segments_4 ---';
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
		RAISE NOTICE '--- run_all_compute_speeds_from_neighborhood_segments ---';
	FOR record IN
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_1')
		UNION ALL
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_areas')
		UNION ALL
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_nodes')
		UNION ALL
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_nodesways')
		UNION ALL
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_2_ways')
		UNION ALL
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_3')
		UNION ALL
		SELECT * FROM mob_group_runtests('_compute_speeds_from_neighborhood_segments_4')
	LOOP
		RETURN NEXT record;
	END LOOP;

END;
$$ LANGUAGE plpgsql;

-- Run tests
-- SELECT * FROM run_all_compute_speeds_from_neighborhood_segments();
