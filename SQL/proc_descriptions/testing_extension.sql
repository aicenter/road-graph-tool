-- Mobility group runtests(): alternative for pgTap.runtests()
-- Mobility group runtests()
-- TODO come up with adequate naming or leave it like that
create function mob_group_runtests(name, text) returns SETOF text
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
END;
$$;

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
END;
$$;
