-- Mobility group runtests(): alternative for pgTap.runtests()
-- Mobility group runtests()
-- TODO come up with adequate naming or leave it like that


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
                findfuncs( $1, startup_pattern ),
                findfuncs( $1, shutdown_pattern ),
                findfuncs( $1, setup_pattern ),
                findfuncs( $1, teardown_pattern ),
                findfuncs( $1, $2, exclude_pattern )
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
            findfuncs( startup_pattern ),
            findfuncs( shutdown_pattern ),
            findfuncs( setup_pattern ),
            findfuncs( teardown_pattern ),
            findfuncs( $1, exclude_pattern )
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
