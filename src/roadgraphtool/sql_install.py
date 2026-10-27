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


_TABLE_DEFINITION = re.compile(r"\bcreate\s+table\s+if\s+not\s+exists\s+\{schema\}\.(\w+)\s*\((.*?)\n\);", re.IGNORECASE | re.DOTALL)
_CONSTRAINT_DEFINITION = re.compile(r"\bconstraint\s+(\"[^\"]+\"|\w+)", re.IGNORECASE)
_INDEX_DEFINITION = re.compile(r"\bcreate\s+(?:unique\s+)?index\s+(?:if\s+not\s+exists\s+)?(\"[^\"]+\"|\w+)\s+on\b", re.IGNORECASE)
_COMMENT = re.compile(r"--[^\n]*")
_TABLE_CONSTRAINT_KEYWORDS = ("constraint", "primary", "unique", "foreign", "check", "exclude")


def _unquote(identifier: str) -> str:
    return identifier[1:-1] if identifier.startswith('"') else identifier.lower()


def _ddl_columns(table_body: str) -> list[str]:
    """Column names declared in the body of a CREATE TABLE statement (one column per line)."""
    columns = []
    for line in table_body.splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.lower().startswith(_TABLE_CONSTRAINT_KEYWORDS):
            continue
        columns.append(_unquote(line.split()[0].rstrip(",")))
    return columns


def _existing_tables(db, schema: str, tables: list[str]) -> set[str]:
    sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema AND table_name = ANY(:tables)"
    return {row[0] for row in db.execute_sql_and_fetch_all_rows(sql, {"schema": schema, "tables": tables})}


def _table_differences(db, schema: str, table_sql: str, tables: dict[str, str]) -> list[str]:
    """Columns, constraints, and indexes declared in the table DDL but missing in the existing tables."""
    differences = []
    for table, body in tables.items():
        columns_sql = "SELECT column_name FROM information_schema.columns WHERE table_schema = :schema AND table_name = :table"
        existing_columns = {row[0] for row in db.execute_sql_and_fetch_all_rows(columns_sql, {"schema": schema, "table": table})}
        differences.extend(
            f"{schema}.{table}: missing column {column}" for column in _ddl_columns(body) if column not in existing_columns
        )

    constraints_sql = """
        SELECT constraints.conname
        FROM pg_constraint AS constraints
            JOIN pg_namespace AS namespaces ON namespaces.oid = constraints.connamespace
        WHERE namespaces.nspname = :schema
    """
    existing_constraints = {row[0] for row in db.execute_sql_and_fetch_all_rows(constraints_sql, {"schema": schema})}
    differences.extend(
        f"missing constraint {constraint}"
        for constraint in map(_unquote, _CONSTRAINT_DEFINITION.findall(table_sql))
        if constraint not in existing_constraints
    )

    indexes_sql = "SELECT indexname FROM pg_indexes WHERE schemaname = :schema"
    existing_indexes = {row[0] for row in db.execute_sql_and_fetch_all_rows(indexes_sql, {"schema": schema})}
    differences.extend(
        f"missing index {index}"
        for index in map(_unquote, _INDEX_DEFINITION.findall(table_sql))
        if index not in existing_indexes
    )
    return differences


def _install_tables(db, sql_dir: Path, schema: str) -> None:
    """Create the tables (and views) of the table DDL files that do not exist yet.

    Existing tables are not changed: if they differ from the DDL (missing columns, constraints, or indexes), the
    installation fails with the list of differences, which have to be resolved manually (e.g., by a migration or by
    recreating the table). Column types are not compared.
    """
    differences = []
    for table_sql_path in sorted((sql_dir / "tables").glob("*.sql")):
        table_sql = _COMMENT.sub("", table_sql_path.read_text(encoding="utf-8"))
        tables = {name.lower(): body for name, body in _TABLE_DEFINITION.findall(table_sql)}
        existing = _existing_tables(db, schema, list(tables))
        if not existing:
            # new tables, or only views and other idempotent statements
            logging.info("Executing %s", table_sql_path)
            db.execute_script(table_sql_path, schema, raise_on_error=True)
        elif len(existing) == len(tables):
            differences.extend(
                f"{table_sql_path.name}: {difference}"
                for difference in _table_differences(db, schema, table_sql, tables)
            )
        else:
            differences.append(
                f"{table_sql_path.name}: only some of the tables exist: {sorted(existing)} of {sorted(tables)}"
            )
    if differences:
        raise RuntimeError(
            f"Existing tables in schema '{schema}' differ from the DDL, resolve the differences manually:\n"
            + "\n".join(differences)
        )


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

