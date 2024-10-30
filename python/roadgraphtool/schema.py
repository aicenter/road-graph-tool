from typing import Optional, TYPE_CHECKING
import psycopg2

import roadgraphtool.db


if TYPE_CHECKING:
    from psycopg2 import connection

TABLES = ["nodes", "ways"]

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
        with db.get_new_psycopg2_connection() as conn:
            with conn.cursor() as cur:
                query = f'CREATE SCHEMA if not exists "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")
    
def add_postgis_extension(schema: str):
    """Adds the PostGIS extension to the specified schema."""
    try:
        with roadgraphtool.db.db.get_new_psycopg2_connection() as conn:
            with conn.cursor() as cur:
                query = f'CREATE EXTENSION if not exists postgis SCHEMA "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def check_empty_or_nonexistent_tables(schema: str, tables: list = TABLES) -> bool:
    """Returns True, if all tables from TABLES are non-existent or empty. 
    Returns False if at least one isn't empty."""
    try:
        with roadgraphtool.db.db.get_new_psycopg2_connection() as conn:
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
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")
