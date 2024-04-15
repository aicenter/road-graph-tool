# Notes regarding pgTap testing framework

## Instalation
1) pgTAP must be installed on a host with PostgreSQL server running; it cannot be installed remotely. If you’re using PostgreSQL in Docker, you need to install pgTAP inside the Docker container.
    If you are using Linux, you may (depending on your distribution) be able to use you distribution’s package management system to install pgTAP. For instance, on Debian, Ubuntu, or Linux Mint pgTAP can be installed with the command:
    `sudo apt-get install pgtap`
    On other systems pgTAP has to be downloaded and built. First, download pgTAP from PGXN (click the green download button in the upper-right). Extract the downloaded zip file, and (at the command line) navigate to the extracted folder.

    To build pgTAP and install it into a PostgreSQL database, run the following commands:

    ``` sh
    make
    make install
    make installcheck
    ```

## Useful Notes

## Notes according my work
1) All tests could be written in one file with extension .sql (maybe tests for every procedure would be seperated in different ) and then one shell script could be executed for testing all of them (maybe even somehow convert it into a function or procedure to test in psql console). P.S. __actually__ it could be done by _Additional functions( useful simplification )_
2) Rather than casually checking return value of the procedure to be the one expected, most of the defined procedures do not return values, thus leaving the only option as to look at the procedure: 
    1. figure out what could be changed, 
    2. save before-call values of the modified tables/rows/columns/cells, 
    3. call the procedure in a sub envrionment, 
    4. check results to be expected,
    5. rollback.
3) Useful functions: `can()`, `function_returns()`, `is_strict()`
4) Useful postgres: Usage of `SAVEPOINT`
5) It is essential to use naming convention. Then particular functions could be called
!!! WARNING VERY IMPORTANT
    Do not run `plan()` or `no_plan()` without entering transaction mode. Tried it out, tests could be run only once per session (it is somehow related to the point that pgTap creates a tmp table, which is not deleted by `finish()` tests).

## TODO list
- [x] Ask if it is preffered to contain tests in `.sql` files + `.sh` file or rather in database functions. A: It is prefferably to use postgres functions to run_tests.
- [ ] Write a test procedure, then try out the above described method to see if there are changes after finishing the tests
- [x] read https://pgtap.org/documentation.html#feelingfunky to get methods with function-oriented testing
- [ ] Ask if we need to test for perfoming in good time by using function `performs_ok()`.
- [x] try out a complicated test with startup, shutdown, setup and teardown functions.
- [ ] Read https://pgtap.org/documentation.html#tapthatbatch once again, when having several testing functions to fully understand the value of the described functions.
- [x] Try out naming convention. I could rewrite names of the existing testing functions
- [ ] Ask about `pg_prove()` utility.

## Picture of a result
- All tests should be saved as postgresql functions.
- On the start of testing (every kind of testing), I think it would be a good idea to check if corresponding tests, setups, startups, teardowns, shutdowns exist with the help of `can()`
- I guess, if indiviudal setups/teardowns are requested, then we should just call them inside of `test_...()` function block on the start/end.

## Commands
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

!!! note Author's note:
    in further functions argument `:description` is optional. Argument `:sql` means an sql statement in singular quotes ''.
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
- `SELECT row_eq(   :sql,   :record,    :description) ` - tests that `sql` query returns identical row as `record`. Basically it compares contents

### The schema assertions
!!! note Author's note: 
    I'm gonna skip this one, as it is highly unlikely, that I would encounter tasks including testing schemas

### Table assertions
!!! note Author's note: 
    This part is mainly about structure, so I'm skipping this one as well.

### Function/procedure assertions
!!! note Author's note:
    This part looks promising!
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
!!! note Author's note:
    this part is about asserting functions of some objects, that cannot be grouped, e.g. superuser assertion, casting assertion and so on.

### Owner assertions
!!! note Author's note:
    this part is about asserting owner of some objects like view, tablespace and so on. 

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
