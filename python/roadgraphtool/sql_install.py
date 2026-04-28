"""
Public API for initializing Road Graph Tool SQL objects in Postgres.

This module is intentionally importable from client projects so they can ensure
the road-graph-tool database schema/functions/tests are installed without relying
on a repo-local script path.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional


def _default_sql_dir() -> Path:
    # If SQL assets are installed into the package (preferred), they should be here.
    pkg_sql = Path(__file__).resolve().parent / "SQL"
    if (pkg_sql / "schema_preamble.sql").exists():
        return pkg_sql

    # When installed from source, the repo layout is:
    # road-graph-tool/python/roadgraphtool/sql_install.py  -> ../../../SQL
    candidate = Path(__file__).resolve().parents[3] / "SQL"
    if (candidate / "schema_preamble.sql").exists():
        return candidate

    # If packaged as a wheel/sdist, SQL assets must be shipped. We don't know the
    # exact packaging strategy, so we keep a clear error message here.
    raise FileNotFoundError(
        "Could not locate road-graph-tool SQL assets. Expected an 'SQL' directory with "
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
    - config.schema: target schema name
    - config.importer.schema: schema used to check whether DB is initialized
    """
    if sql_dir is None:
        sql_dir = _default_sql_dir()

    import_schema = config.importer.schema
    schema = config.schema

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

    exists_sql = f"""SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = '{import_schema}' AND table_name = 'areas'
        );
        """
    if not db.execute_sql_and_fetch_all_rows(exists_sql)[0][0]:
        logging.info("Initializing the database")
        _execute_sql_file(db, sql_dir / "schema_preamble.sql", schema, multistatement=True)
        for table_sql_path in sorted((sql_dir / "tables").glob("*.sql")):
            _execute_sql_file(db, table_sql_path, schema, multistatement=True)

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

