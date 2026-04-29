CREATE EXTENSION IF NOT EXISTS pgtap;

-- Mobility group runtests(): alternative for pgTap.runtests()

CREATE OR REPLACE FUNCTION findfuncs_recursive(schema_name name, pattern text, exclude_pattern text) returns text[]
    language plpgsql
as
$$
DECLARE
    excluded_patterns TEXT[];
    funcs TEXT[];
    excluded_funcs TEXT[];
    funcs_sub TEXT[];
    split_pattern TEXT[];
    new_pattern TEXT;
    i INT;
BEGIN
    -- create patterns: e.g. given pattern = '^startup_get_ways_in_target_area_no_target_area'
    -- the resulting funcs[] should contain:
    -- ['^startup_get_ways_in_target_area_no_target_area$', '^startup_get_ways_in_target_area_no_target$', '^startup_get_ways_in_target_area_no$',
    -- '^startup_get_ways_in_target_area$', '^startup_get_ways_in_target$', '^startup_get_ways_in$', '^startup_get_ways$', '^startup_get$']
    -- Split the pattern by underscores
    split_pattern := string_to_array(pattern, '_');

    -- get all functions that match the pattern
    -- Loop through the split pattern
    FOR i IN 2..array_length(split_pattern, 1)
        LOOP
            -- Create a new pattern by joining the split pattern with underscores
            new_pattern := array_to_string(split_pattern[1:i], '_');

            -- Add a caret at the start and a dollar sign at the end of the new pattern
            new_pattern := new_pattern || '$';

            -- Get all functions that match the new pattern
            FOR funcs_sub IN
                SELECT CASE WHEN schema_name IS NULL THEN findfuncs(new_pattern) ELSE findfuncs(schema_name, new_pattern) END -- if schema_name is NULL, then search in all schemas
                LOOP
                    -- Add the found funcs to the funcs array
                    funcs := funcs || funcs_sub;
                END LOOP;
        END LOOP;

    -- Now we need to exclude functions that match the exclusion pattern
    IF exclude_pattern IS NOT NULL THEN
        -- parse exclusion_pattern into excluded_patterns
        excluded_patterns := string_to_array(substring(exclude_pattern, 3, length(exclude_pattern) - 3), '|');
        -- Get all functions that match the exclusion pattern
        FOR i IN 1..array_length(excluded_patterns, 1)
            LOOP
                -- Get all functions that match the exclusion pattern
                FOR excluded_funcs IN
                    SELECT * FROM findfuncs_recursive(schema_name, '^' || excluded_patterns[i])
                    LOOP
                        -- Add the found funcs to the excluded_funcs array
                        excluded_funcs := excluded_funcs || excluded_funcs;
                    END LOOP;
            END LOOP;
    END IF;

    -- Remove the excluded functions from the funcs array
    funcs := ARRAY (SELECT unnest(funcs) EXCEPT SELECT unnest(excluded_funcs) ORDER BY 1);

    -- Return the funcs array
    RETURN funcs;
END;
$$;

CREATE OR REPLACE FUNCTION findfuncs_recursive(schema_name name, pattern text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
    BEGIN
    RETURN findfuncs_recursive(schema_name, pattern, NULL);
    END;
$$;


CREATE OR REPLACE FUNCTION findfuncs_recursive(pattern text, exclude_pattern text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN findfuncs_recursive(NULL, pattern, exclude_pattern);
END;
$$;

CREATE OR REPLACE FUNCTION findfuncs_recursive(pattern text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
    BEGIN
    RETURN findfuncs_recursive(NULL, pattern, NULL);
    END;
$$;


-- Function: mob_group_runtests(name, text)
-- This function is used to run a group of tests.
-- Input parameters: name - the name of the schema to look for the test functions;
--                   text - the pattern to match the names of the functions to run.
-- Flow:
-- 1. Run alphabetically ordered startup functions once, which match the pattern "startup" + $2.
-- 2. Enter a loop:
--  2.1. Run alphabetically ordered setup functions once, which match the pattern "setup" + $2.
--  2.2. Run alphabetically ordered test functions once, which match the pattern $2.
--  2.3. Run alphabetically ordered teardown functions once, which match the pattern "teardown" + $2.
-- 3. Run alphabetically ordered shutdown functions once, which match the pattern "shutdown" + $2.
-- 4. Return the results of the tests.
create or replace function mob_group_runtests(schema_name name, filter text) returns SETOF text
    language plpgsql
as
$$
DECLARE
    startup TEXT := 'startup_' || filter;
    shutdown TEXT := 'shutdown_' || filter;
    setup TEXT := 'setup_' || filter;
    teardown TEXT := 'teardown_' || filter;
    test TEXT := 'test_' || filter;
    startup_pattern TEXT := '^' || startup;
    shutdown_pattern TEXT := '^' || shutdown;
    setup_pattern TEXT := '^' || setup;
    test_pattern TEXT := '^' || test;
    teardown_pattern TEXT := '^' || teardown;
    exclude_pattern TEXT := '^(' || startup || '|' || shutdown || '|' || setup || '|' || teardown || ')';
    result_record RECORD;
BEGIN
    -- create testing environment:
    CALL _env_constructor();

    FOR result_record IN
        SELECT * FROM _runner(
            findfuncs_recursive( schema_name, startup_pattern ),
            findfuncs_recursive( schema_name, shutdown_pattern ),
            findfuncs_recursive( schema_name, setup_pattern ),
            findfuncs_recursive( schema_name, teardown_pattern ),
            findfuncs_recursive( schema_name, test_pattern, exclude_pattern )
        )
    LOOP
        RETURN NEXT result_record;
    END LOOP;

    -- trigger the rollback
    RAISE EXCEPTION 'Roll back triggered' USING ERRCODE = 'T0000';
EXCEPTION
    WHEN SQLSTATE 'T0000' THEN
        -- do nothing, just rollback
        RAISE NOTICE 'Rolling back...';
END;
$$;

-- Function: mob_group_runtests(text)
-- This function is used to run a group of tests.
-- Input parameters: text - the pattern to match the names of the functions to run.
-- Flow:
-- 1. Run alphabetically ordered startup functions once, which match the pattern "startup" + $1.
-- 2. Enter a loop:
--  2.1. Run alphabetically ordered setup functions once, which match the pattern "setup" + $1.
--  2.2. Run alphabetically ordered test functions once, which match the pattern $1.
--  2.3. Run alphabetically ordered teardown functions once, which match the pattern "teardown" + $1.
-- 3. Run alphabetically ordered shutdown functions once, which match the pattern "shutdown" + $1.
-- 4. Return the results of the tests.
create or replace function mob_group_runtests(filter text) returns SETOF text
    language plpgsql
as
$$
DECLARE
    record RECORD;
BEGIN
    FOR record IN
        SELECT * FROM mob_group_runtests(NULL, filter)
    LOOP
        RETURN NEXT record;
    END LOOP;
END;
$$;

-- procedures for creating testing environment

CREATE OR REPLACE PROCEDURE _env_constructor(text) AS
$$
DECLARE
    test_scheme_name TEXT := $1;
    table_name_i TEXT;
    object RECORD;
BEGIN
    -- schema should exist already as a prerequisite
    -- check that given schema name is not empty
    IF test_scheme_name = '' THEN
        RAISE EXCEPTION 'Schema name should not be empty';
    END IF;

    -- check that given schema has no tables containing at least one row
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = test_scheme_name) THEN
        RAISE EXCEPTION 'Schema % should not contain any tables', test_scheme_name;
    END IF;

    -- check if schema exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = test_scheme_name) THEN
        RAISE EXCEPTION 'Schema % does not exist. Please create test scheme...', test_scheme_name;
    END IF;

    FOR table_name_i IN (SELECT table_name FROM information_schema.tables WHERE table_schema = 'public')
        LOOP
            -- Create the table with the same structure
            EXECUTE format('CREATE TABLE %I.%I (LIKE public.%I INCLUDING ALL)',
                       test_scheme_name, table_name_i, table_name_i);

        END LOOP;


    -- Copy sequences
    FOR object IN
        SELECT sequence_name::text FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        LOOP
            EXECUTE 'CREATE SEQUENCE ' || quote_ident(test_scheme_name) || '.' || quote_ident(object.sequence_name) ||
                    ' AS INTEGER';
        END LOOP;

    -- update search path. In the end it should look like: "test_env, \"$user\", public",
    --  so it would look up the tables in test_env and routines in public
    EXECUTE format('SET search_path TO %I, %I, public', test_scheme_name, '$user');
END;
$$
    LANGUAGE plpgsql;

CREATE OR REPLACE PROCEDURE _env_constructor() AS
$$
BEGIN
    -- call with default value
    CALL _env_constructor('test_env');
END;
$$
    LANGUAGE plpgsql;
