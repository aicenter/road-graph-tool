# Notes regarding pgTap testing framework

1. [Installation](#installation)
    - [Installing pgTap for PostgreSQL on Windows](#installing-pgtap-for-postgresql-on-windows)

2. [Useful Notes](#useful-notes)

3. [Commands](#commands)
    - [Basic assertions](#basic-assertions)
    - [Exception handling assertions](#exception-handling)
    - [Comparison assertions](#comparasion-assertions)
    - [Function/procedure assertions](#functionprocedure-assertions)
    - [Additional functions (Diagnostics)](#additional-functions-diagnostics)
    - [Additional functions (Conditional Tests)](#additional-functions-conditional-tests)
    - [Additional functions (Useful Simplification)](#additional-functions-useful-simplification)
    - [Additional functions (Running Tests)](#additional-functions-running-tests)

## Installation
1) pgTAP must be installed on a host with PostgreSQL server running; it cannot be installed remotely. If you’re using PostgreSQL in Docker, you need to install pgTAP inside the Docker container.
    If you are using Linux, you may (depending on your distribution) be able to use you distribution’s package management system to install pgTAP. For instance, on Debian, Ubuntu, or Linux Mint pgTAP can be installed with the command:
    `sudo apt-get install pgtap`\
    On other systems pgTAP has to be downloaded and built. First, download pgTAP from [PGXN](https://pgxn.org/dist/pgtap/) (click the green download button in the upper-right). Extract the downloaded zip file, and (at the command line) navigate to the extracted folder.

    To build pgTAP and install it into a PostgreSQL database, run the following commands:

    ``` sh
    make
    make install
    make installcheck
    ```

### Installing pgtap for PostgreSQL on Windows

To install pgtap for PostgreSQL on Windows, follow these steps:

1. **Download and extract Strawberry Perl**

   Visit the [Strawberry Perl releases page](https://strawberryperl.com/releases.html) and download the Portable 64-bit version. Extract the downloaded archive to a folder named `{strawberryperl}`.

   ![Strawberry Perl download](https://user-images.githubusercontent.com/1125565/140190878-5d23c9d5-7d6d-4c49-9ede-09833813845e.png)

2. **Clone the pgtap repository**

   Clone the pgtap repository from GitHub using the following command:

   ```
   git clone https://github.com/theory/pgtap.git {pgtapFolder}
   ```

3. **Open Command Prompt as Administrator**

   Run `cmd.exe` as an Administrator to ensure you have the necessary permissions to copy files into the `ProgramFiles` directory.

4. **Launch the Strawberry Perl portable shell**

   Navigate to the `{strawberryperl}` folder (extracted in step 1) and run `portableshell.bat`.

5. **Prepare and copy the necessary files**

   In the portable shell, execute the following commands:

   ```sh
   cd {pgtapFolder}
   copy sql\pgtap.sql.in sql\pgtap.sql
   perl.exe -pi.bak -e "s/TAPSCHEMA/tap/g" sql\pgtap.sql
   perl.exe -pi.bak -e "s/__OS__/win32/g" sql\pgtap.sql
   perl.exe -pi.bak -e "s/__VERSION__/0.24/g" sql\pgtap.sql
   perl.exe -pi.bak -e "s/^-- ## //g" sql\pgtap.sql
   copy sql\pgtap.sql "%ProgramFiles%\PostgreSQL\12\share\extension"
   copy contrib\pgtap.spec  "%ProgramFiles%\PostgreSQL\12\contrib"
   copy pgtap.control "%ProgramFiles%\PostgreSQL\12\share\extension"
   cd "%ProgramFiles%\PostgreSQL\12\share\extension\"
   ren "pgtap.sql" "pgtap--1.2.0.sql"
   ```

   **Note:** The `copy` commands may differ depending on your system configuration.

   If you encounter an error like "error: extension "pgtap" has no installation script nor update path for version "{version}", modify the last step to `ren "pgtap.sql" "pgtap--{version}.sql"`.

These instructions were adapted from [issue#192](https://github.com/theory/pgtap/issues/192#issuecomment-960033060) of the pgtap repository.

## Useful Notes

- There are five types of testing functions in PostgreSQL:

    - `startup`: These functions run in alphabetical order before any test functions are executed.
    - `setup`: Functions in this category run in alphabetical order before each test function.
    - `test`: These functions must include at least one pgTap assertion command.
    - `teardown`: Functions in this group run in alphabetical order after each test function. However, they are skipped if a test has failed.
    - `shutdown`: Functions in this category run in alphabetical order after all test functions have been executed.

- Please refer to the [Commands section](#commands) for a list of available pgTap assertions.

!!! note Author's Note
    This section provides crucial information regarding the naming and execution of testing functions. Subsequent sections may contain additional information, but it is recommended to prioritize the guidelines outlined here.

- Instead of using the built-in pgTap function `runtests(...)`, you can utilize the `mob_group_runtests(...)` function provided in the `testing_extension.sql` file. This alternative offers several advantages:

    - It provides an additional layer of safety by rolling back any modifications made by `startup` and `shutdown` functions that may not be reverted by the original `runtests(...)` function.
    - It enforces a strict naming convention for testing functions, allowing for hierarchical grouping:
        - All testing functions should begin with either `startup`, `setup`, `test`, `teardown`, or `shutdown`.
        - Hierarchical structure is established using underscores (_) in function names. For example:
          `startup_get_ways_in_target_area()`, `setup_get_ways_in_target_area_no_target_area()`, or
          `test_get_ways_in_target_area_no_ways_intersecting_target_area()`.
        - Now, let's dive into the execution process. Consider a scenario where you have defined only three testing functions as outlined in the previous section. When you execute the query `SELECT * FROM mob_group_runtests('_get_ways_in_target_area_no_target_area');`, the `mob_group_runtests` function searches across all schemas for functions that match specific regular expressions, following a guaranteed order. These regular expressions are constructed as follows:
            1) `^(startup|setup|test|teardown|shutdown)_get$`
            2) `^(startup|setup|test|teardown|shutdown)_get_ways$`
            3) Continuing in this pattern until it reaches: `^(startup|setup|test|teardown|shutdown)_get_ways_in_target_area_no_target_area$`
    - You can specify the schema for `mob_group_runtests(...)` to search for testing functions by adding an additional argument. For example:
      `SELECT * FROM mob_group_runtests('test_schema', '_get_ways_in_target_area_no_target_area');` would search only in the schema named `test_schema`.

## Picture of a result
- All tests should be saved as postgresql functions.
- On the start of testing (every kind of testing), I think it would be a good idea to check if corresponding tests, setups, startups, teardowns, shutdowns exist with the help of `can()`
- I guess, if indiviudal setups/teardowns are requested, then we should just call them inside of `test_...()` function block on the start/end.

## Commands
- Please refer to [official documentation](https://pgtap.org/documentation.html) for additional information
- Declaring number of tests script is going to run: `Select plan(42)`. If not known use `SELECT * FROM no_plan();`. Ofthen you can count number of tests like so: `SELECT plan( COUNT(*) ) FROM foo;`
- In the end of tests you should always use `SELECT * FROM finish()`. To end with an exception use true argument: `SELECT * FROM finish(true);`
- You can run all unit tests at any time using `runtests()`. E.g. of statement: `SELECT * FROM runtests();`. Each test function will run within its own transaction.
- You can customize test names by overriding `diag_test_name(TEXT)` function like so: 
``` sql
CREATE OR REPLACE FUNCTION diag_test_name(TEXT)
RETURNS TEXT AS $$
    SELECT diag('test: ' || $1 );
$$ LANGUAGE SQL;
```
Note: This will show something like 
``` 
# test: my_example_test_function_name
```
instead of
```
# my_example_test_function_name()
```
- Sequences are not rolled back to the value used at the beginning of a rolled-back transaction.

- __in further functions argument `:description` is optional. Argument `:sql` means an sql statement in singular quotes ''.__

### Basic assertions
- `SELECT ok( :boolean, :description )` - returns either "ok - description" or "not ok - description" based on a resulting evaluation of boolean expression (NULL equals TRUE).
- `SELECT is( :have,    :want,  :description )` or `SELECT isnt( :have,    :want,  :description )` - compares two args `:have` and `:want` of the same data type and returns diagnostics of the test simillar to `ok()` function return value.
Note: usage of `is()` and `isnt()` is preffered over `ok()`
- `SELECT matches( :have,   :regex, :description );` - compares arg `:have` with a regular expression `:regex`.
- `SELECT imatches( :have,  :regex, :description );` - same as `matches`, but case-insensitive.
- `SELECT doesnt_match( :have,  :regex, :description );` or `SELECT doesnt_imatch( :have,  :regex, :description );` simillar to `matches()` and `imatches()`, but in negative context.
- `SELECT alike(    :have,  :like,  :description );` or `SELECT ialike(    :have,  :like,  :description );` - simillar to `matches()` and `imatches()`, using SQL LIKE pattern instead of regex.
- `SELECT unalike(  :have,  :like,  :description );` or `SELECT unialike(    :have,  :like,  :description );` - simillar to `doesnt_match()` and `doesnt_imatch()`, using SQL LIKE pattern instead of regex.
- `SELECT cmp_ok(   :have,  :op,    :want,  :description)` - compares two args `:have`, `:want` using any binary operator like `=`, `>=` or `&&`.
- `SELECT pass( :decsription );` or `SELECT fail(   :description );` - prints passed or failed test (description). Like `print_info_message()` or `print_error_message()`.

### Exception handling
- `SELECT isa_ok(   :have,  :regtype,   :name );` - checks to see if the given value is of a particular type. E. g. `SELECT isa_ok( length('foo'), 'integer', 'The return value from length')`
- `SELECT throws_ok(    :sql,   :errcode,   :ermsg, :description )` - tests for throwing an exception. Argument `:errcode` is taken from [Appendix A of PostgreSql documentation](https://www.postgresql.org/docs/current/static/errcodes-appendix.html)
- `SELECT throws_like(  :sql,   :like,  :description )` or `throws_ilike(...)` - same as `throws_ok()`, but tests an exception message for a match to an SQL LIKE pattern.
- `SELECT throws_matching(  :sql,   :regex, :description )` or `throws_imatching(...)` - same as `throws_like()`, but instead of matching SQL LIKE pattern, matches regex pattern. 
- `SELECT lives_ok( :sql,   :description );` - The inverse of throws_ok(), ensures that `:sql` statement does not throw exception.
- `SELECT performs_ok(  :sql,   :milliseconds,  :description )` - The function makes sure that `:sql` statement performs well by failing when timeout is occured, which is specified with argument `:milliseconds`.
- `SELECT performs_within(  :sql, :average_milliseconds,    :within,    :iterations, :description);` - Function executes `:sql` statement 10 times, and calculates if the average execution time is within the specified window.

### Comparasion assertions
- `SELECT results_eq(...,   :description)`, where `...` has different variations such as: `:sql, :sql`, `:sql, :array`, `:cursor, :cursor`, `:sql, :cursor`, `:cursor, :array`. A direct row-by-row comaprison of results to ensure integrity and order of the data.
- `SELECT results_ne(...,   :description)`, The inverse of `results_eq()` 
- `SELECT set_eq(...,   :description)`, same as `results_eq`, but order does not matter
- `SELECT set_ne(...,   :description)`, same as `results_ne`, but order does not matter
- `SELECT set_has( :sql,    :sql,   :description) ` - to test if the first `sql` query returns everything from the 2nd `sql` query.
- `SELECT set_hasnt( :sql,  :sql,   :description) ` - the inverse of `set_has`.
- `SELECT bag_eq( :sql,     :sql,   :description) ` - same as `set_has`, but considers also duplicates, if 2 duplicated rows appear in 1st `sql` query, 2 of these rows should appear in the 2nd.
- `SELECT bag_ne( :sql,     :sql,   :description) ` - the inverse of `bag_ne()`
- `SELECT is_empty( :sql,   :description) ` - tests that `:sql` query returns no records
- `SELECT isnt_empty( :sql,   :description) ` - tests that `:sql` query returns at least one record
- `SELECT row_eq(   :sql,   :record,    :description) ` - tests that `sql` query returns identical row as `record`. Basically it compares contents

### The schema assertions
This type of assertions is skipped due to low probability of usage. Please refer to official documentation for information. 

### Table assertions
This type of assertions is skipped due to low probability of usage. Please refer to official documentation for information. 

### Function/procedure assertions
- `SELECT can( :schema, :functions, :description )` or `SELECT can( :functions, :description )` - Checks that `:schema` has `:functions` defined. If `:schema` is not defined, this assertion will look through all schemas defined in the search path. 
- `SELECT function_lang_is( :schema,    :function,  :args,  :language)` - checks that function is implemented in a particular procedural language.
- `SELECT function_returns( :schema?,   :function,  :args?, :type,  :description)` - tests that a particular function returns a particular data type.
- `SELECT is_definer( :schema?, :function,  :args?, :description)` - tests that a function or procedure is a security definer.
- `SELECT isnt_definer( :schema?, :function,  :args?, :description)` - the inverse of `is_definer()`
- `SELECT is_strict( :schema?,  :function,  :args?, :description)` - tests that a function is a strict AKA returns null if any argument is null.
- `SELECT isnt_strict( :schema?,    :function,  :args?, :description)` - the inverse of `is_strict()`
- `SELECT is_normal_function( :schema?, :function,  :args?, :description)` - tests that a function is not an aggregate, window or procedureal function
- `SELECT isnt_normal_function( :schema?,   :function,  :args?, :description)` - the inverse of `is_normal_function()`
- `SELECT is_aggregate( :schema?,   :function,  :args?, :description)` - tests if a function is an aggregate function
- `SELECT isnt_aggregate( :schema?,   :function,  :args?, :description)` - the inverse of `is_aggreagte()`
- `SELECT is_window( :schema?,  :function,  :args?, :description)` - tests if a function is a window function
- `SELECT isnt_window( :schema?,    :function,  :args?, :description)` - the inverse of `is_window()`
- `SELECT is_procedure( :schema?,   :function,  :args?, :description)` - tests if a function is a procedural function.
- `SELECT isnt_procedure( :schema?, :function,  :args?, :description)` - the inverse of `is_procedure()`.
- `SELECT volatility_is( :schema?,  :function,  :args?, :volatility,    :description)` - tests if the function has given `:volatility` level
- `SELECT trigger_is( :schema?, :table?,    :trigger,   :func_schema,   :function,  :description)` - tests that the specified trigger calls the named function.

### Other object assertions
This type of assertions is skipped due to low probability of usage. Please refer to official documentation for information. 

### Owner assertions
This type of assertions is skipped due to low probability of usage. Please refer to official documentation for information. 

### Additional functions( Diagnostics )
- `SELECT diag( :lines )`, where `:lines` is a list of one or more SQL values of the same type.\
For example:
``` sql
-- Output a diagnostic message if the collation is not en_US.UTF-8.
SELECT diag(
     E'These tests expect LC_COLLATE to be en_US.UTF-8,\n',
     'but yours is set to ', setting, E'.\n',
     'As a result, some tests may fail. YMMV.'
)
  FROM pg_settings
 WHERE name = 'lc_collate'
   AND setting <> 'en_US.UTF-8';
```
which outputs
``` 
# These tests expect LC_COLLATE to be en_US.UTF-8,
# but yours is set to en_US.ISO8859-1.
# As a result, some tests may fail. YMMV.
```

### Additional functions( Conditional Tests )
- `SELECT skip( :why,   :how_many )` - is used to skip tests for a reason up to the author of the tests. `:how_many` specifies a number of tests to be skipped, it is actually used for a `plan` function to understand that test function were suppossed to run, but due to some reasons were skipped.
- `SELECT todo( :why,   :how_many )` - declares a series of tests that you expect to fail and why. Tests will be run as usual, but pgTap will add a flag that these tasts are in progress due to a bug or not finished assertion.\
A series of __todo__ functions to use, when we find it difficult to specify the number of tests that are TODO tests:
- `SELECT todo_start( :description )` - declares a starting point of _unsure waters_ 
- `SELECT todo_end()` - declares an ending point of _unsure waters_
!!! note
    `todo_start()` should always be followed by `todo_end()`, otherwise fatal outcome is ensured.
- `in_todo()` returns __true__ if it is called from inside of testing block.

### Additional functions( useful simplification )
There is a method to group tests into a blocks and then test it from sql query console. Example:
```sql
CREATE OR REPLACE FUNCTION my_tests(
) RETURNS SETOF TEXT AS $$
BEGIN
    RETURN NEXT pass( 'plpgsql simple' );
    RETURN NEXT pass( 'plpgsql simple 2' );
END;
$$ LANGUAGE plpgsql;
```
Then you call the function to run all of the specified TAP tests at once:
```sql
SELECT plan(2);
SELECT * FROM my_tests();
SELECT * FROM finish();
```

### Additional functions( Running tests )
__runtests():__
```sql
SELECT runtests( :schema, :pattern );
SELECT runtests( :schema );
SELECT runtests( :pattern );
SELECT runtests( );
```
- `runtests()` fully supports startup, shutdown, setup, and teardown functions, as well as transactional rollbacks between tests. It also outputs the test plan, executes each test function as a TAP subtest, and finishes the tests, so you don’t have to call `plan()` or `finish()` yourself.
- The fixture functions run by runtests() are as follows:
    - `^startup` - Functions whose names start with “startup” are run in alphabetical order before any test functions are run.
    - `^setup` - Functions whose names start with “setup” are run in alphabetical order before each test function is run.
    - `^teardown` - Functions whose names start with “teardown” are run in alphabetical order after each test function is run. They will not be run, however, after a test that has died.
    - `^shutdown` - Functions whose names start with “shutdown” are run in alphabetical order after all test functions have been run.
!!! note
    - all tests executed by `runtests()` are run within a single transaction, and each test is run in a subtransaction that also includes execution all the setup and teardown functions
    - All transactions are rolled back after each test function, and at the end of testing.
    - Startup modifications are not cleaned automatically (tried it out without shutdown). Here is an [issue](https://groups.google.com/g/pgtap-users/c/enU925h6cxU/m/fb0-S3kqBwAJ) mailed to pgTap users.
