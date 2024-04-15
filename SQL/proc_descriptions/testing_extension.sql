-- Mobility group runtests(): alternative for pgTap.runtests()
-- Mobility group runtests()
-- TODO come up with adequate naming or leave it like that

CREATE OR REPLACE FUNCTION findfuncs_recursive(name, text, text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
DECLARE
    schema_name ALIAS FOR $1;
    pattern ALIAS FOR $2;
    exclusion_pattern ALIAS FOR $3; -- example of pattern: ^(startup_get_ways_in_target_area_no_target_area|shutdown_get_ways_in_target_area_no_target_area|setup_get_ways_in_target_area_no_target_area|teardown_get_ways_in_target_area_no_target_area)
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
            SELECT * FROM findfuncs(schema_name, new_pattern)
        LOOP
            -- Add the found funcs to the funcs array
            funcs := funcs || funcs_sub;
        END LOOP;
    END LOOP;

    -- Now we need to exclude functions that match the exclusion pattern
    IF exclusion_pattern IS NOT NULL THEN
        -- parse exclusion_pattern into excluded_patterns
        excluded_patterns := string_to_array(substring(exclusion_pattern, 3, length(exclusion_pattern) - 3), '|');
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
    funcs := ARRAY (SELECT unnest(funcs) EXCEPT SELECT unnest(excluded_funcs));

    -- Return the funcs array
    RETURN funcs;
END;
$$;

CREATE OR REPLACE FUNCTION findfuncs_recursive(name, text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
    BEGIN
    RETURN findfuncs_recursive($1, $2, NULL);
    END;
$$;


CREATE OR REPLACE FUNCTION findfuncs_recursive(text, text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
DECLARE
    pattern ALIAS FOR $1;
    exclusion_pattern ALIAS FOR $2; -- example of pattern: ^(startup_get_ways_in_target_area_no_target_area|shutdown_get_ways_in_target_area_no_target_area|setup_get_ways_in_target_area_no_target_area|teardown_get_ways_in_target_area_no_target_area)
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
            SELECT * FROM findfuncs(new_pattern)
        LOOP
            -- Add the found funcs to the funcs array
            funcs := funcs || funcs_sub;
        END LOOP;
    END LOOP;

    -- Now we need to exclude functions that match the exclusion pattern
    IF exclusion_pattern IS NOT NULL THEN
        -- parse exclusion_pattern into excluded_patterns
        excluded_patterns := string_to_array(substring(exclusion_pattern, 3, length(exclusion_pattern) - 3), '|');
        -- Get all functions that match the exclusion pattern
        FOR i IN 1..array_length(excluded_patterns, 1)
        LOOP
            -- Get all functions that match the exclusion pattern
            FOR excluded_funcs IN
                SELECT * FROM findfuncs_recursive('^' || excluded_patterns[i])
            LOOP
                -- Add the found funcs to the excluded_funcs array
                excluded_funcs := excluded_funcs || excluded_funcs;
            END LOOP;
        END LOOP;
    END IF;

    -- Remove the excluded functions from the funcs array
    funcs := ARRAY (SELECT unnest(funcs) EXCEPT SELECT unnest(excluded_funcs));

    -- Return the funcs array
    RETURN funcs;
END;
$$;

CREATE OR REPLACE FUNCTION findfuncs_recursive(text) RETURNS text[]
    LANGUAGE plpgsql
AS
$$
    BEGIN
    RETURN findfuncs_recursive($1, NULL);
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
create or replace function mob_group_runtests(name, text) returns SETOF text
    language plpgsql
as
$$
DECLARE
    startup TEXT := 'startup' || $2;
    shutdown TEXT := 'shutdown' || $2;
    setup TEXT := 'setup' || $2;
    teardown TEXT := 'teardown' || $2;
    startup_pattern TEXT := '^' || startup;
    shutdown_pattern TEXT := '^' || shutdown;
    setup_pattern TEXT := '^' || setup;
    teardown_pattern TEXT := '^' || teardown;
    exclude_pattern TEXT := '^(' || startup || '|' || shutdown || '|' || setup || '|' || teardown || ')';
    result_record RECORD;
BEGIN
    -- A little note about raising exception in this function, it seems that `_runner` function
    -- does not raise an exception, instead catching it and returning it as a record, so under
    -- this assumption we raise "division by zero" AKA "22012" exception to rollback the transaction.
    BEGIN -- begin transaction for later rollback
        FOR result_record IN
            SELECT * FROM _runner(
                findfuncs_recursive( $1, startup_pattern ),
                findfuncs_recursive( $1, shutdown_pattern ),
                findfuncs_recursive( $1, setup_pattern ),
                findfuncs_recursive( $1, teardown_pattern ),
                findfuncs_recursive( $1, $2, exclude_pattern )
            )
        LOOP
            RETURN NEXT result_record;
        END LOOP;

        -- Raise the exception
        RAISE EXCEPTION '__TAP_ROLLBACK__' USING ERRCODE = '22012';
    EXCEPTION
        WHEN SQLSTATE '22012' THEN
            -- Catch the exception to prevent it from propagating
            NULL; -- Do nothing
    END;
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
create or replace function mob_group_runtests(text) returns SETOF text
    language plpgsql
as
$$
DECLARE
    startup TEXT := 'startup' || $1;
    shutdown TEXT := 'shutdown' || $1;
    setup TEXT := 'setup' || $1;
    teardown TEXT := 'teardown' || $1;
    test TEXT := 'test' || $1;
    startup_pattern TEXT := '^' || startup;
    shutdown_pattern TEXT := '^' || shutdown;
    setup_pattern TEXT := '^' || setup;
    teardown_pattern TEXT := '^' || teardown;
    test_pattern TEXT := '^' || test;
    exclude_pattern TEXT := '^(' || startup || '|' || shutdown || '|' || setup || '|' || teardown || ')';
    result_record RECORD;
BEGIN
    -- A little note about raising exception in this function, it seems that `_runner` function
    -- does not raise an exception, instead catching it and returning it as a record, so under
    -- this assumption we raise "division by zero" AKA "22012" exception to rollback the transaction.
    BEGIN -- begin transaction for later rollback
    FOR result_record IN
        SELECT * FROM _runner(
            findfuncs_recursive( startup_pattern ),
            findfuncs_recursive( shutdown_pattern ),
            findfuncs_recursive( setup_pattern ),
            findfuncs_recursive( teardown_pattern ),
            findfuncs_recursive( test_pattern, exclude_pattern )
        )
    LOOP
        RETURN NEXT result_record;
    END LOOP;
        -- Raise the exception
        RAISE EXCEPTION '__TAP_ROLLBACK__' USING ERRCODE = '22012';
    EXCEPTION
        WHEN SQLSTATE '22012' THEN
            -- Catch the exception to prevent it from propagating
            NULL; -- Do nothing
    END;
END;
$$;
