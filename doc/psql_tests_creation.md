# Writing tests with PgTap

## Manual TODO list:
- [x] Optional execution of `testing_extension.sql` for increased productivity.
- [ ] Test functions return type, naming hierarchy.
- [ ] Running tests. Write about both PgTap `runtests` & Mobility group's `mob_group_runtests`
- [ ] PgTap manual assertions.
- [ ] Warning notes. (if there are any).
- [ ] add some examples to every section

## Manual structure
- [ ] Intro.
- [x] Prerequisites.
- [ ] Function requirement.
- [ ] Assertions.
- [ ] Running tests. How is `runtests` and `mob_group_runtests` are built.
- [ ] Some notes. Warnings etc.

## Prerequisites

In order to start creating tests for the procedure/function you should have installed PgTap framework against your postgresql database. Please review [installation section](./pgtap.md#installation) in order to progress.
Another thing we highly recommend, but is not essential, is to add to your database all functions from [testing_extension.sql](../SQL/testing_extension.sql). This file contains helper functions, which adds another layer of safety over PgTap safety measurements to your database data.

## Test function requirements

For PgTap framework to work correctly you should apply several rules, when writing testing functions:
- Naming convention. Underscore dependency. Kinds of functions.
- Return Type. <!-- TODO: review this in official documentation. -->

## Assertions

- assertions from pgtap.md

## Running tests

- `runtests`, `mob_group_runtests`.

