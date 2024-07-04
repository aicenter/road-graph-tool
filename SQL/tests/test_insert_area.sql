CREATE OR REPLACE FUNCTION startup_insert_area() RETURNS VOID AS
$$
BEGIN
  -- create temp table containing data for each case
  CREATE TEMP TABLE test_insert_area_data(
    name VARCHAR,
    geom JSON,
    id INTEGER,
    description VARCHAR
  );

  -- insert data
  INSERT INTO test_insert_area_data VALUES(
    'test1',
    '{"type":"MultiPolygon","coordinates":[[[[0,0],[0,1],[1,1],[0,0]]]]}',
    1,
    'test1'
  ),
  (
    'test2_1',
    '{"type":"MultiPolygon","coordinates":[[[[0,0],[0,1],[1,1],[0,0]]]]}',
    2,
    'test2_1'
  ),
  (
    'test2_2',
    '{"type":"MultiPolygon","coordinates":[[[[0,0],[0,-1],[-1,-1],[0,0]]]]}',
    2,
    'test2_2'
  ),
  (
    'test3',
    '{"type":"MultiPolygon","coordinates":[[[[0,0],[0,1],[1,1],[0,0]]]]}',
    NULL,
    NULL
  ),
  (
    'test4',
    '{"type":"Point","coordinates":[0,0]}',
    3,
    'test4'
  );
END;
$$ LANGUAGE plpgsql;

-- 1. valid input paramaters
CREATE OR REPLACE FUNCTION test_insert_area_valid_all() RETURNS SETOF TEXT AS
$$
DECLARE
    test_data RECORD;
    num_records INTEGER;
BEGIN
  RAISE NOTICE '--- test_insert_area_valid_all ---';
  SELECT * FROM test_insert_area_data WHERE name = 'test1' INTO test_data;
  PERFORM insert_area(test_data.name, test_data.geom, test_data.id, test_data.description);

  -- check that the record was inserted
  SELECT count(1) INTO num_records FROM areas;

  RETURN NEXT is(num_records, 1, 'Count of records in `areas` is 1');
END;
$$ LANGUAGE plpgsql;

-- 2. valid input with existing id -> shouldn't modify table
CREATE OR REPLACE FUNCTION test_insert_area_valid_existing_id() RETURNS SETOF TEXT AS
$$
DECLARE
    test_data RECORD;
    num_records INTEGER;
BEGIN
    RAISE NOTICE '--- test_insert_area_valid_existing_id ---';
    SELECT * FROM test_insert_area_data WHERE name = 'test2_1' INTO test_data;
    PERFORM insert_area(test_data.name, test_data.geom, test_data.id, test_data.description);

    -- check that the record was inserted
    SELECT count(1) INTO num_records FROM areas;

    RETURN NEXT is(num_records, 1, 'Prerequisite: Count of records in `areas` is 1');

    -- Now check for throwing when inserting record with the same id
    RETURN NEXT diag('Expecting an error due to failing unique constraint of the table');
    RETURN NEXT throws_ok('SELECT insert_area(test_data.name, test_data.geom, test_data.id, test_data.description)' ||
                          ' FROM test_insert_area_data test_data WHERE name = ''test2_2'';', '23505');
END;
$$ LANGUAGE plpgsql;

-- 3. valid input with only mandatory parameters 
CREATE OR REPLACE FUNCTION test_insert_area_valid_mandatory_params() RETURNS SETOF TEXT AS
$$
DECLARE
  test_data RECORD;
  num_records INTEGER;
BEGIN
  RAISE NOTICE '--- test_insert_area_valid_mandatory_params ---';
  SELECT * FROM test_insert_area_data WHERE name = 'test3' INTO test_data;
  PERFORM insert_area(test_data.name, test_data.geom, test_data.id, test_data.description);

  -- check that the record was inserted
  SELECT count(1) INTO num_records FROM areas;

  RETURN NEXT is(num_records, 1, 'Inserted record with mandatory parameters only.');
END;
$$ LANGUAGE plpgsql;

-- 4. invalid input: given geom is not of type geometry(MultiPolygon) 
CREATE OR REPLACE FUNCTION test_insert_area_invalid_geom() RETURNS SETOF TEXT AS
$$
BEGIN
  RAISE NOTICE '--- test_insert_area_invalid_geom ---';
  RETURN NEXT diag('Expecting an error due to invalid geom type');
  RETURN NEXT throws_ok('SELECT insert_area(test_data.name, test_data.geom, test_data.id, test_data.description)' ||
                        ' FROM test_insert_area_data test_data WHERE name = ''test4'';', '22023');
END;
$$ LANGUAGE plpgsql;

-- run all tests of the function
CREATE OR REPLACE FUNCTION run_all_insert_area_tests() RETURNS SETOF TEXT AS
$$
BEGIN
  -- runtests
  RETURN QUERY SELECT * FROM mob_group_runtests('_insert_area_.*');
END;
$$ LANGUAGE plpgsql;
