import logging
from pathlib import Path

import roadgraphtool.log
from roadgraphtool.db import db

db_name = db.db_name
sql_dir = Path(__file__).parent.parent.parent / "SQL"


def execute_sql_file(sql_file: Path, multistatement: bool = False):
    logging.info(f"Executing {sql_file}")
    if multistatement:
        db.execute_script(sql_file)
    else:
        with sql_file.open() as f:
            sql = f.read()
            db.execute_sql(sql)


logging.basicConfig(level=logging.INFO)

# Check availability status of extensions in db
logging.info("Checking availability of extensions in the database")
extension_list = ["postgis", "pgrouting", "hstore", "pgtap"]

sql = f"""
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
for extension_name, status in db.execute_sql_and_fetch_all_rows(sql):
    logging.info(f"{extension_name}: {status}")
    extensions[extension_name] = status == "Available"

# Assert that critically needed extensions are present
if not extensions["postgis"] or not extensions["pgrouting"] or not extensions["hstore"]:
    raise Exception("Missing critical extensions")

# initialize database if it's empty
sql = f"""SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'areas'
        );
        """
if not db.execute_sql_and_fetch_all_rows(sql)[0][0]:
    main_sql_path = sql_dir / "main.sql"
    logging.info("Initializing the database")
    execute_sql_file(main_sql_path, multistatement=True)

# enable pgtap if it's not enabled
sql = """SELECT * FROM pg_extension WHERE extname = 'pgtap'"""
if extensions["pgtap"] and not db.execute_sql_and_fetch_all_rows(sql):
    logging.info("Enabling pgtap")
    execute_sql_file(sql_dir / "testing_extension.sql", multistatement=True)
else:
    if not extensions["pgtap"]:
        logging.warning("pgtap extension is not available")
    else:
        logging.info("pgtap extension is already enabled")

# Create test schema if it doesn't exist
sql = """SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'test_env')"""
if not db.execute_sql_and_fetch_all_rows(sql)[0][0]:
    logging.info("Creating test schema")
    db.execute_sql("CREATE SCHEMA test_env")

functions_dir = sql_dir / "functions"
logging.info("Importing functions from %s", functions_dir)
for sql_function_file in functions_dir.rglob("*.sql"):
    execute_sql_file(sql_function_file)

procedures_dir = sql_dir / "procedures"
logging.info("Importing procedures from %s", procedures_dir)
for sql_procedure_file in procedures_dir.rglob("*.sql"):
    execute_sql_file(sql_procedure_file)

test_dir = sql_dir / "tests"
logging.info("Importing test functions from %s", test_dir)
for sql_test_file in test_dir.rglob("*.sql"):
    execute_sql_file(sql_test_file, multistatement=True)
