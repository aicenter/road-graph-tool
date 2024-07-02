# Writing tests with PgTap

<!-- TODO: table of contents -->

## Manual TODO list:
- [x] Optional execution of `testing_extension.sql` for increased productivity.
- [x] Test functions return type, naming hierarchy.
- [x] Running tests. Write about both PgTap `runtests` & Mobility group's `mob_group_runtests`
- [x] PgTap manual assertions.
- [ ] formalise everything with LLM.
- [ ] Add table of contents

## Manual structure
- [ ] Intro.
- [x] Prerequisites.
- [x] Function requirement.
- [x] Assertions.
- [x] Running tests. How is `runtests` and `mob_group_runtests` are built.
- [ ] Some notes. Warnings etc.

## Prerequisites

In order to start creating tests for the procedure/function you should have installed PgTap framework against your postgresql database. Please review [installation section](./pgtap.md#installation) in order to progress.

---
Another thing we highly recommend, but is not essential, is to add to your database all functions from [testing_extension.sql](../SQL/testing_extension.sql). This file contains helper functions, which add another layer of safety over PgTap safety measurements to your database data.

## Test function requirements

For PgTap framework to work correctly you should apply several rules, when writing testing functions:
- Naming convention. These set of rules exist due to a concept, on which process of tests' execution is built. Basically, when running tests `runtests()` or `mob_group_runtests()` function looks for specified functions in the schemas provided in search path of the SQL console.
    - Kinds of functions. There are five types of testing functions in PostgreSQL:
        - `startup`: These functions run in alphabetical order before any test functions are executed.
        - `setup`: Functions in this category run in alphabetical order before each test function.
        - `test`: These functions must include at least one pgTap assertion command.
        - `teardown`: Functions in this group run in alphabetical order after each test function. However, they are skipped if a test has failed.
        - `shutdown`: Functions in this category run in alphabetical order after all test functions have been executed.
- Return Type. PgTap assertions' results are returned as a column of TEXT, not to stdout or stderr, that's why there is a need to represent testing scenarios as postgres functions (not procedures) and return type should be `SETOF TEXT`. That means that all `test` functions should return `SETOF TEXT`, but other types of functions could return anything as their return value is ignored.

## Assertions

PgTap provides a wide variety of possible assertions, useful part of which you could find in our [short review](./pgtap.md#commands) of the official documentation. 

## Running tests

PgTap extension provides `runtests()` function as a way to execute particular tests. On the other hand we provide `mob_group_runtests()`, lets look at the source code of these functions.

### `runtests()`
```sql
create function runtests(text) returns SETOF text
    language sql
as
$$
    SELECT * FROM _runner(
        findfuncs( '^startup' ),
        findfuncs( '^shutdown' ),
        findfuncs( '^setup' ),
        findfuncs( '^teardown' ),
        findfuncs( $1, '^(startup|shutdown|setup|teardown)' )
    );
$$;
```
Pretty straightforward. This function calls another functions, which receives 5 arguments:
1. An array of `startup` functions. It looks for all functions in the schemas (which are defined by search path) that begin with `startup`.
2. An array of `shutdown` functions. It looks for all functions in the schemas (which are defined by search path) that begin with `shutdown`.
3. An array of `setup` functions. It looks for all functions in the schemas (which are defined by search path) that begin with `setup`.
4. An array of `teardown` functions. It looks for all functions in the schemas (which are defined by search path) that begin with `teardown`.
5. An array of `test` functions. It looks for all functions that match pattern given by first argument and excludes from this list all functions, that match pattern `^(startup|shutdown|setup|teardown)`. 

You should be highly warned, when using `runtests()`, as this function executes all found `startup`, `shutdown`, `setup` and `shutdown` functions independently from given argument pattern. Consider this example:
```sql
CREATE OR REPLACE FUNCTION startup_foo() returns VOID AS
$$
BEGIN
    -- startup of foo testing function
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION startup_bar() returns VOID AS
$$
BEGIN
    -- startup of bar testing function
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_foo() RETURNS SETOF TEXT AS
$$
BEGIN
    -- testing of foo function
    pass('Foo function is valid');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_bar() RETURNS SETOF TEXT AS
$$
BEGIN
    -- testing of bar function
    pass('Bar function is valid');
END;
$$ LANGUAGE plpgsql;
```
Now running tests for `foo()` function:

```sql
SELECT * FROM runtests('^test_foo$');
-- Results in this execution order:
-- 1. startup_bar()
-- 2. startup_foo()
-- 3. test_foo()
```

Which is not something we would like. That's why we adapted `runtests()` function resulting in `mob_group_runtests()`.

### `runtests()`
```sql
create function mob_group_runtests(name, text) returns SETOF text
    language plpgsql
as
$$
DECLARE
    startup TEXT := 'startup' || $2;
    shutdown TEXT := 'shutdown' || $2;
    setup TEXT := 'setup' || $2;
    teardown TEXT := 'teardown' || $2;
    test TEXT := 'test' || $2;
    startup_pattern TEXT := '^' || startup;
    shutdown_pattern TEXT := '^' || shutdown;
    setup_pattern TEXT := '^' || setup;
    test_pattern TEXT := '^' || test;
    teardown_pattern TEXT := '^' || teardown;
    exclude_pattern TEXT := '^(' || startup || '|' || shutdown || '|' || setup || '|' || teardown || ')';
    result_record RECORD;
BEGIN
    -- create testing environment:
    CALL test_env_constructor();

    -- A little note about raising exception in this function, it seems that `_runner` function
    -- does not raise an exception, instead catching it and returning it as a record, so under
    -- this assumption we raise "successful_completion" AKA "00000" exception to rollback the transaction.
    BEGIN -- begin transaction for later rollback
        FOR result_record IN
            SELECT * FROM _runner(
                findfuncs_recursive( $1, startup_pattern ),
                findfuncs_recursive( $1, shutdown_pattern ),
                findfuncs_recursive( $1, setup_pattern ),
                findfuncs_recursive( $1, teardown_pattern ),
                findfuncs_recursive( $1, test_pattern, exclude_pattern )
            )
        LOOP
            RETURN NEXT result_record;
        END LOOP;

        -- Raise the exception
        RAISE EXCEPTION '__TAP_ROLLBACK__' USING ERRCODE = '00000';
    EXCEPTION
        WHEN SQLSTATE '00000' THEN
            -- Catch the exception to prevent it from propagating
            NULL; -- Do nothing
    END;

    -- destroy testing environment:
    CALL test_env_destructor();
END;
$$;
```

The main concept stays the same as in function `runtests()`, but we add several useful things:
1. Safety:
    - As an original `runtests()` does not provide rollback of actions made by `startup` and `teardown` functions, we aritificially force an exception to rollback those changes.
    - Instead of testing in the main schema, we move every action to a schema, which is by defualt called `test_env`. This provides an opportunity to execute testing actions without interfering with existing data and also exclude possible changes to objects, which are couldn't be rolled back by PostgreSQL such as sequences.
2. Features:
    - Now there is dependency on the given pattern for `startup`, `shutdown`, `setup` adn `teardown` function.
    - Function hierarchy. We've implemented hierarchical grouping with the help of underscores `_`. Consider this example:
```sql
CREATE OR REPLACE FUNCTION startup_foo() RETURNS VOID AS
$$
BEGIN
    -- startup of foo
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION startup_bar() RETURNS VOID AS
$$
BEGIN
    -- startup of bar
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_foo_foo() RETURNS VOID AS
$$ 
BEGIN
    -- setup of foo. Special case foo_foo
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_foo_fooooo() RETURNS VOID AS
$$
BEGIN
    -- setup of foo. Special case foo_fooooo
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_foo_foo_2() RETURNS SETOF TEXT AS
$$
BEGIN
    -- testing foo. Special case foo_foo_2
    RETURN NEXT pass('Passsed foo_foo_2');
END;
$$ LANGUAGE plpgsql;
```

Running test of special case `foo_foo_2` would look like this:
```sql
SELECT * FROM mob_group_runtests('_foo_foo_2');
-- Execution order:
-- 1. startup_foo();
-- 2. setup_foo_foo();
-- 3. test_foo_foo_2();
```

For more information on how hierarchial grouping works please refer to [useful notes section](./pgtap.md#useful-notes) of our PgTap guide.
