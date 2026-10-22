import logging
from typing import Optional, TYPE_CHECKING
import psycopg2

import roadgraphtool.db
from roadgraphtool.exceptions import MissingInputError


if TYPE_CHECKING:
    from psycopg2 import connection

TABLES = ["nodes", "ways"]


def schema_exists(schema: str) -> bool:
    rows = roadgraphtool.db.db.execute_sql_and_fetch_all_rows(
        "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :schema)", {"schema": schema}
    )
    return bool(rows[0][0])


def ensure_schema(config) -> None:
    """Make sure the schema configured in the root ``schema`` parameter exists.

    If it does not exist, raise ``MissingInputError``, unless the root parameter ``create_schema`` is ``true``.
    In that case, create the schema and install the Road Graph Tool tables, functions, and procedures into it.
    The database user then needs the ``CREATE`` privilege on the database (see ``roadgraphtool.privileges``).
    """
    schema = config.schema
    if schema_exists(schema):
        return

    if not getattr(config, "create_schema", False):
        raise MissingInputError(
            f"Schema '{schema}' does not exist in database '{config.db.db_name}'. Check the root parameter "
            "`schema`, or set the root parameter `create_schema: true` to create it."
        )

    from roadgraphtool.sql_install import install_sql

    logging.info("Creating schema '%s' and installing the Road Graph Tool SQL objects into it", schema)
    create_schema(schema)
    install_sql(config=config, db=roadgraphtool.db.db, include_tests=False)

# def get_connection() -> Optional['connection']:
#     """Establishes a connection to the database and returns the connection object."""
#     try:
#         connection = psycopg2.connect(
#             dbname=config.db_name,
#             user=config.username,
#             password=config.db_password,
#             host=config.db_host,
#             port=config.db_server_port
#         )
#         return connection
#     except psycopg2.DatabaseError as error:
#         raise Exception(f"Error connecting to the database: {str(error)}")


def create_schema(schema: str):
    """Creates a new schema in the database."""

    db = roadgraphtool.db.db

    try:
        with db._get_new_psycopg2_connection() as conn:
            with conn.cursor() as cur:
                query = f'CREATE SCHEMA if not exists "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")
    
def add_postgis_extension(schema: str):
    """Adds the PostGIS extension to the specified schema."""
    try:
        with roadgraphtool.db.db._get_new_psycopg2_connection() as conn:
            with conn.cursor() as cur:
                query = f'CREATE EXTENSION if not exists postgis SCHEMA "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def check_empty_or_nonexistent_tables(schema: str, tables: list = TABLES) -> bool:
    """Returns True, if all tables from TABLES are non-existent or empty. 
    Returns False if at least one isn't empty."""
    with roadgraphtool.db.db._get_new_psycopg2_connection() as conn:
        with conn.cursor() as cur:
            for t in tables:
                query =  f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = '{schema}' AND table_name = '{t}');"
                cur.execute(query)
                exists = cur.fetchone()[0]
                if exists:
                    query = f"SELECT EXISTS (SELECT  * FROM {schema}.{t} limit 1) as has_data;"
                    cur.execute(query)
                    has_data = cur.fetchone()[0]
                    if has_data: # at least one table from TABLES exists and isn't empty
                        return False
    return True

