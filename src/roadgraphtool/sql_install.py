"""
Public API for initializing Road Graph Tool SQL objects in Postgres.

This module is intentionally importable from client projects so they can ensure
the road-graph-tool database schema/functions/tests are installed without relying
on a repo-local script path.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_SQL_DIR = Path(__file__).resolve().parent / "SQL"
"""The SQL assets shipped in the package."""


def _check_sql_dir(sql_dir: Path) -> None:
    # without this check, a wrong directory installs nothing without any error
    if not (sql_dir / "schema_preamble.sql").exists():
        raise FileNotFoundError(
            f"Could not locate road-graph-tool SQL assets in {sql_dir}. Expected an 'SQL' directory with "
            "'schema_preamble.sql'. If you installed roadgraphtool as a package, make sure SQL "
            "files are included in the distribution."
        )


def _execute_sql_file(db, sql_file: Path, schema: str, multistatement: bool = False) -> None:
    logging.info("Executing %s", sql_file)
    if multistatement:
        db.execute_script(sql_file, schema)
    else:
        sql = sql_file.read_text(encoding="utf-8").replace("{schema}", schema)
        db.execute_sql(sql, schema=schema)


_ROUTINE_DEFINITION = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?(?:function|procedure)\s+(?:[\w{}\"]+\.)?\"?(\w+)\"?\s*\(",
    re.IGNORECASE,
)


def _drop_routines(db, sql_files: Iterable[Path], schema: str) -> None:
    """Drop all functions and procedures in *schema* named as the ones defined in *sql_files*.

    ``CREATE OR REPLACE`` can neither change the return type or the parameter names of a routine, nor remove its
    previous overloads when the signature changes, so the routines are dropped and created again. Without
    ``CASCADE``: if another object depends on a routine, the installation fails. Privileges granted on the routines
    are dropped too (see ``scripts/grant_privileges.py``).
    """
    names = sorted({
        name
        for sql_file in sql_files
        for name in _ROUTINE_DEFINITION.findall(sql_file.read_text(encoding="utf-8"))
    })
    routines_sql = """
        SELECT format('%I.%I(%s)', namespaces.nspname, routines.proname, pg_get_function_identity_arguments(routines.oid))
        FROM pg_proc AS routines
            JOIN pg_namespace AS namespaces ON namespaces.oid = routines.pronamespace
        WHERE namespaces.nspname = :schema AND routines.proname = ANY(:names) AND routines.prokind IN ('f', 'p')
        ORDER BY 1
    """
    routines = [row[0] for row in db.execute_sql_and_fetch_all_rows(routines_sql, {"schema": schema, "names": names})]
    logging.info("Dropping %s existing functions and procedures before installing them again", len(routines))
    for routine in routines:
        db.execute_sql(f"DROP ROUTINE {routine}", schema=schema)


_TABLE_DEFINITION = re.compile(
    r"\bcreate\s+table\s+if\s+not\s+exists\s+\{schema\}\.(\w+)\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL
)
_CONSTRAINT_DEFINITION = re.compile(
    r"\balter\s+table\s+(?:only\s+)?\{schema\}\.(\w+)\s+add\s+constraint\s+(\"[^\"]+\"|\w+)\s+(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_INDEX_DEFINITION = re.compile(
    r"\bcreate\s+(unique\s+)?index\s+(?:if\s+not\s+exists\s+)?(\"[^\"]+\"|\w+)\s+on\s+(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_INDEX_NAME = re.compile(r"\bindex\s+(?:\"[^\"]+\"|\w+)\s+on\b", re.IGNORECASE)
_IDEMPOTENT_STATEMENT = re.compile(
    r"\b(?:create\s+sequence\s+if\s+not\s+exists|create\s+or\s+replace\s+view|comment\s+on"
    r"|alter\s+table\s+(?:only\s+)?\S+\s+alter\s+column\s+\S+\s+set)\b",
    re.IGNORECASE,
)
_COMMENT = re.compile(r"--[^\n]*")
_TABLE_CONSTRAINT_KEYWORDS = ("constraint", "primary", "unique", "foreign", "check", "exclude")


def _unquote(identifier: str) -> str:
    return identifier[1:-1] if identifier.startswith('"') else identifier.lower()


def _statements(sql: str) -> list[str]:
    """The non-empty statements of *sql*, split on the semicolons outside of string literals."""
    statements = []
    start = 0
    in_string = False
    for position, char in enumerate(sql):
        if char == "'":
            in_string = not in_string
        elif char == ";" and not in_string:
            statements.append(sql[start:position])
            start = position + 1
    statements.append(sql[start:])
    return [statement.strip() for statement in statements if statement.strip()]


def _ddl_columns(table_body: str) -> dict[str, str]:
    """Column names and their definitions declared in the body of a CREATE TABLE statement (one column per line)."""
    columns = {}
    for line in table_body.splitlines():
        line = line.strip().rstrip(",")
        if not line or line.lower().startswith(_TABLE_CONSTRAINT_KEYWORDS):
            continue
        columns[_unquote(line.split()[0])] = line
    return columns


def _existing_columns(db, schema: str, table: str) -> Optional[set[str]]:
    """The columns of the existing table, or ``None`` if the table does not exist."""
    sql = """
        SELECT columns.column_name
        FROM information_schema.tables
            LEFT JOIN information_schema.columns USING (table_schema, table_name)
        WHERE table_schema = :schema AND table_name = :table
    """
    rows = db.execute_sql_and_fetch_all_rows(sql, {"schema": schema, "table": table})
    if not rows:
        return None
    return {row[0] for row in rows if row[0] is not None}


def _existing_constraints(db, schema: str) -> dict[str, dict[str, tuple[str, str]]]:
    """The constraints of the tables in *schema*: table name -> constraint name -> (constraint type, definition)."""
    sql = """
        SELECT tables.relname, constraints.conname, constraints.contype, pg_get_constraintdef(constraints.oid)
        FROM pg_constraint AS constraints
            JOIN pg_class AS tables ON tables.oid = constraints.conrelid
            JOIN pg_namespace AS namespaces ON namespaces.oid = tables.relnamespace
        WHERE namespaces.nspname = :schema
    """
    constraints: dict[str, dict[str, tuple[str, str]]] = {}
    for table, name, constraint_type, definition in db.execute_sql_and_fetch_all_rows(sql, {"schema": schema}):
        constraints.setdefault(table, {})[name] = (constraint_type, definition)
    return constraints


def _existing_indexes(db, schema: str) -> dict[str, str]:
    """The indexes in *schema*: index name -> definition (``CREATE INDEX`` statement)."""
    sql = "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = :schema"
    return {row[0]: row[1] for row in db.execute_sql_and_fetch_all_rows(sql, {"schema": schema})}


def _normalize_definition(definition: str, schema: str) -> str:
    """The constraint or index definition in a form comparable between the DDL and the catalog: without schema
    qualification, identifier quotes, and case and whitespace differences."""
    definition = definition.replace("{schema}.", "").replace(f"{schema}.", "")
    definition = re.sub(r"\s+", " ", definition.lower()).replace('"', "")
    return re.sub(r"\s*([(),])\s*", r"\1", definition).strip()


def _constraint_statements(
    statement: str, table: str, name: str, definition: str, existing: dict[str, tuple[str, str]], schema: str
) -> list[str]:
    """The statements making the constraint *name* with *definition* of the ``ADD CONSTRAINT`` *statement* exist on
    *table*, given the table's *existing* constraints (name -> (type, definition)): none if it exists, a rename if
    it exists under another name, a replacement if its definition changed or if another primary key exists, and the
    addition otherwise."""
    alter = f"ALTER TABLE ONLY {{schema}}.{table}"
    add = f"ADD CONSTRAINT {name} {definition}"
    normalized = _normalize_definition(definition, schema)
    existing_definition = existing.get(_unquote(name))
    if existing_definition is not None:
        if _normalize_definition(existing_definition[1], schema) == normalized:
            return []
        return [f"{alter} DROP CONSTRAINT {name}, {add}"]
    for other, (_, other_definition) in existing.items():
        if _normalize_definition(other_definition, schema) == normalized:
            return [f'{alter} RENAME CONSTRAINT "{other}" TO {name}']
    if normalized.startswith("primary key"):
        for other, (constraint_type, _) in existing.items():
            if constraint_type == "p":
                return [f'{alter} DROP CONSTRAINT "{other}", {add}']
    return [statement]


def _index_statements(statement: str, unique: bool, name: str, definition: str, existing: dict[str, str], schema: str) -> list[str]:
    """The statements making the index *name* with *definition* (the part after ``ON``) of the ``CREATE INDEX``
    *statement* exist, given the *existing* indexes (name -> definition): none if it exists (its definition is not
    compared), a rename if an index with the same definition exists under another name, and the creation otherwise.
    """
    if _unquote(name) in existing:
        return []
    normalized = _normalize_definition(f"create {'unique ' if unique else ''}index on {definition}", schema)
    for other, other_definition in existing.items():
        if _normalize_definition(_INDEX_NAME.sub("index on", other_definition), schema) == normalized:
            return [f'ALTER INDEX {{schema}}."{other}" RENAME TO {name}']
    return [statement]


def _update_statements(
    db,
    schema: str,
    table_sql: str,
    existing_constraints: dict[str, dict[str, tuple[str, str]]],
    existing_indexes: dict[str, str],
) -> list[str]:
    """The statements of the table DDL *table_sql* that make the schema match the DDL without dropping anything.

    ``CREATE TABLE`` statements of existing tables are replaced by ``ALTER TABLE ... ADD COLUMN`` statements for the
    columns missing in the table (table constraints declared in the table body are not added); constraints and
    indexes are added, renamed, or replaced as described in ``_constraint_statements`` and ``_index_statements``;
    the other statements (sequences, views, comments, column defaults and options) are idempotent by themselves.
    """
    statements = []
    for statement in _statements(_COMMENT.sub("", table_sql)):
        table_definition = _TABLE_DEFINITION.match(statement)
        constraint_definition = _CONSTRAINT_DEFINITION.match(statement)
        index_definition = _INDEX_DEFINITION.match(statement)
        if table_definition:
            table = table_definition.group(1).lower()
            existing_columns = _existing_columns(db, schema, table)
            if existing_columns is None:
                statements.append(statement)
            else:
                statements.extend(
                    f"ALTER TABLE {{schema}}.{table} ADD COLUMN {definition}"
                    for column, definition in _ddl_columns(table_definition.group(2)).items()
                    if column not in existing_columns
                )
        elif constraint_definition:
            table, name, definition = constraint_definition.groups()
            table = table.lower()
            statements.extend(
                _constraint_statements(
                    statement, table, name, definition.strip(), existing_constraints.get(table, {}), schema
                )
            )
        elif index_definition:
            unique, name, definition = index_definition.groups()
            statements.extend(_index_statements(statement, bool(unique), name, definition, existing_indexes, schema))
        elif _IDEMPOTENT_STATEMENT.match(statement):
            statements.append(statement)
        else:
            raise RuntimeError(f"Unsupported statement in the table DDL:\n{statement}")
    return statements


def _install_tables(db, sql_dir: Path, schema: str) -> None:
    """Create the tables (and views) of the table DDL files and add what the existing tables lack.

    The DDL files are executed statement by statement (one transaction per file): the missing columns of existing
    tables are added with ``ALTER TABLE ... ADD COLUMN``, constraints and indexes that exist under another name are
    renamed, constraints whose definition changed (or primary keys replacing a differently named one) are dropped and
    added again, and the ones that already exist are skipped (see ``_update_statements``). No data is touched:
    columns, constraints, and indexes that exist in the database but not in the DDL are kept, and column types are
    not compared. If the database refuses a change (e.g., a primary key on a table with duplicate keys, a NOT NULL
    column without a default on a table with rows, or dropping a key referenced by a foreign key), the installation
    fails with the database error, and the difference has to be resolved manually.
    """
    existing_constraints = _existing_constraints(db, schema)
    existing_indexes = _existing_indexes(db, schema)
    for table_sql_path in sorted((sql_dir / "tables").glob("*.sql")):
        table_sql = table_sql_path.read_text(encoding="utf-8")
        statements = _update_statements(db, schema, table_sql, existing_constraints, existing_indexes)
        if not statements:
            logging.debug("%s: nothing to add", table_sql_path.name)
            continue
        logging.info("Executing %s statements of %s", len(statements), table_sql_path)
        for statement in statements:
            logging.debug("%s", statement)
        db.execute_statements(statements, schema)


def install_sql(
    *,
    config,
    db,
    sql_dir: Optional[Path] = None,
    include_tests: bool = True,
) -> None:
    """
    Install road-graph-tool SQL assets into the configured database.

    Requirements on config:
    - config.schema: target schema name. The schema must exist (see ``roadgraphtool.schema.ensure_schema``).
    """
    if sql_dir is None:
        sql_dir = DEFAULT_SQL_DIR
    _check_sql_dir(sql_dir)
    logging.info("Installing the Road Graph Tool SQL from %s", sql_dir)

    schema = config.schema

    schema_exists_sql = "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :schema)"
    if not db.execute_sql_and_fetch_all_rows(schema_exists_sql, {"schema": schema})[0][0]:
        # without this check, the unqualified functions and procedures would silently end up in `public`
        raise RuntimeError(f"Schema '{schema}' does not exist. Create it first (root config parameter create_schema).")

    logging.info("Checking availability of extensions in the database")
    extension_list = ["postgis", "pgrouting", "hstore", "pgtap"]
    ext_sql = f"""
WITH extension_list(name) AS (
  VALUES
    {','.join(f"('{ext}')" for ext in extension_list)}
)
SELECT
  el.name AS extension_name,
  CASE
    WHEN ae.name IS NOT NULL THEN 'Available'
    ELSE 'Not Available'
  END AS status
FROM extension_list el
LEFT JOIN pg_available_extensions ae ON el.name = ae.name
ORDER BY el.name;
"""

    extensions = {}
    for extension_name, status in db.execute_sql_and_fetch_all_rows(ext_sql):
        logging.info("%s: %s", extension_name, status)
        extensions[extension_name] = status == "Available"

    if not extensions["postgis"] or not extensions["pgrouting"] or not extensions["hstore"]:
        raise RuntimeError("Missing critical extensions (postgis, pgrouting, hstore) on the database server")

    # The extensions are database-wide. Creating them (and commenting on them in the preamble) requires
    # admin rights, so the preamble only runs when one of them is not installed yet.
    installed_sql = "SELECT count(*) FROM pg_extension WHERE extname IN ('postgis', 'pgrouting', 'hstore')"
    if db.execute_sql_and_fetch_all_rows(installed_sql)[0][0] < 3:
        logging.info("Installing the extensions")
        _execute_sql_file(db, sql_dir / "schema_preamble.sql", schema, multistatement=True)

    logging.info("Installing the Road Graph Tool tables in schema '%s'", schema)
    _install_tables(db, sql_dir, schema)

    if include_tests:
        pgtap_enabled_sql = "SELECT * FROM pg_extension WHERE extname = 'pgtap'"
        if extensions["pgtap"] and not db.execute_sql_and_fetch_all_rows(pgtap_enabled_sql):
            logging.info("Enabling pgtap")
            _execute_sql_file(db, sql_dir / "tests" / "testing_extension.sql", schema, multistatement=True)
        else:
            if not extensions["pgtap"]:
                logging.warning("pgtap extension is not available")
            else:
                logging.info("pgtap extension is already enabled")

        test_schema_exists_sql = "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'test_env')"
        if not db.execute_sql_and_fetch_all_rows(test_schema_exists_sql)[0][0]:
            logging.info("Creating test schema")
            db.execute_sql("CREATE SCHEMA test_env", schema="public")

    routine_dirs = [sql_dir / "functions", sql_dir / "procedures"]
    if include_tests:
        routine_dirs.append(sql_dir / "tests")
    _drop_routines(db, [sql_file for routine_dir in routine_dirs for sql_file in routine_dir.rglob("*.sql")], schema)

    functions_dir = sql_dir / "functions"
    logging.info("Importing functions from %s", functions_dir)
    for sql_function_file in functions_dir.rglob("*.sql"):
        _execute_sql_file(db, sql_function_file, schema)

    procedures_dir = sql_dir / "procedures"
    logging.info("Importing procedures from %s", procedures_dir)
    for sql_procedure_file in procedures_dir.rglob("*.sql"):
        _execute_sql_file(db, sql_procedure_file, schema)

    if include_tests:
        test_dir = sql_dir / "tests"
        logging.info("Importing test functions from %s", test_dir)
        for sql_test_file in test_dir.rglob("*.sql"):
            _execute_sql_file(db, sql_test_file, schema, multistatement=True)

        data_dir = sql_dir / "tests" / "data"
        if data_dir.exists():
            logging.info("Uploading test graphs from %s", data_dir)
            for graphml_file in data_dir.rglob("*.graphml"):
                graph_name = graphml_file.stem
                logging.info("Uploading graph: %s", graph_name)
                content = graphml_file.read_text(encoding="utf-8")
                upload_sql = """
                INSERT INTO test_graphs (name, content)
                VALUES (:graph_name, :xml_content)
                ON CONFLICT (name) DO UPDATE
                SET content = EXCLUDED.content;
                """
                db.execute_sql(upload_sql, {"graph_name": graph_name, "xml_content": content}, schema=schema)

