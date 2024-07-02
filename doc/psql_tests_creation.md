# Writing Tests with PgTap

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Test Function Requirements](#test-function-requirements)
   - [Naming Convention](#naming-convention)
   - [Return Type](#return-type)
3. [Assertions](#assertions)
4. [Running Tests](#running-tests)
   - [`runtests()`](#runtests)
   - [`mob_group_runtests()`](#mob_group_runtests)
5. [Examples](#examples)

## Prerequisites

Before creating tests for procedures or functions, ensure that:

1. The PgTap framework is installed against your PostgreSQL database. Refer to the [installation section](./pgtap.md#installation) for details.

2. (Recommended) Add all functions from [testing_extension.sql](../SQL/testing_extension.sql) to your database. These helper functions provide an additional layer of safety for your database data.

## Test Function Requirements

To ensure PgTap works correctly, adhere to the following rules when writing testing functions:

### Naming Convention

The naming convention is crucial due to how the test execution process is built. When running tests, the `runtests()` or `mob_group_runtests()` function searches for specified functions in the schemas provided in the search path of the SQL console.

There are five types of testing functions in PostgreSQL:

1. `startup`: Run in alphabetical order before any test functions.
2. `setup`: Run in alphabetical order before each test function.
3. `test`: Must include at least one pgTap assertion command.
4. `teardown`: Run in alphabetical order after each test function. Skipped if a test fails.
5. `shutdown`: Run in alphabetical order after all test functions have been executed.

### Return Type

PgTap assertions' results are returned as a column of TEXT, not to stdout or stderr. Therefore:

- All `test` functions must return `SETOF TEXT`.
- Other function types can return anything, as their return value is ignored.

## Assertions

PgTap provides a wide variety of assertions. Refer to our [short review](./pgtap.md#commands) of the official documentation for commonly used assertions.

## Running Tests

PgTap provides the `runtests()` function to execute tests. We also provide `mob_group_runtests()` as an alternative. Let's examine both:

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

This function calls another function with 5 arguments, searching for various function types based on their prefixes.

**Warning**: `runtests()` executes all found `startup`, `shutdown`, `setup`, and `teardown` functions independently of the given argument pattern.

### `mob_group_runtests()`

```sql
create function mob_group_runtests(name, text) returns SETOF text
    language plpgsql
as
$$
-- ... (full function code omitted for brevity)
$$;
```

This function adapts `runtests()` with additional features:

1. Safety:
   - Forces an exception to rollback changes made by `startup` and `teardown` functions.
   - Moves testing actions to a separate schema (default: `test_env`) to avoid interfering with existing data.

2. Features:
   - Adds dependency on the given pattern for `startup`, `shutdown`, `setup`, and `teardown` functions.
   - Implements hierarchical grouping using underscores `_`.

For more information on hierarchical grouping, refer to the [useful notes section](./pgtap.md#useful-notes) of our PgTap guide.

## Examples

```sql
-- Example of function hierarchy
CREATE OR REPLACE FUNCTION startup_foo() RETURNS VOID AS
$$ BEGIN
    -- startup of foo
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION startup_bar() RETURNS VOID AS
$$ BEGIN
    -- startup of bar
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_foo_foo() RETURNS VOID AS
$$ BEGIN
    -- setup of foo. Special case foo_foo
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_foo_fooooo() RETURNS VOID AS
$$ BEGIN
    -- setup of foo. Special case foo_fooooo
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_foo_foo_1() RETURNS SETOF TEXT AS
$$ BEGIN
    -- testing foo. Special case foo_foo_1
    RETURN NEXT pass('Passsed foo_foo_1');
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_foo_foo_2() RETURNS SETOF TEXT AS
$$ BEGIN
    -- testing foo. Special case foo_foo_2
    RETURN NEXT pass('Passsed foo_foo_2');
END; $$ LANGUAGE plpgsql;

-- Running test of special case foo_foo_2
SELECT * FROM runtests('foo_foo_2');
-- Execution order:
-- 1. startup_bar()
-- 2. startup_foo()
-- 3. setup_foo_foo()
-- 4. setup_foo_fooooo()
-- 5. test_foo_foo_2()

SELECT * FROM mob_group_runtests('_foo_foo_2');
-- Execution order:
-- 1. startup_foo();
-- 2. setup_foo_foo();
-- 3. test_foo_foo_2();
```
