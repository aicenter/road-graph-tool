from typing import Optional, TYPE_CHECKING
import psycopg2
from roadgraphtool.credentials_config import CredentialsConfig

if TYPE_CHECKING:
    from psycopg2 import connection

TABLES = ["nodes", "ways"]

class TableNotEmptyError(Exception):
    pass

def get_connection(config: CredentialsConfig) -> Optional['connection']:
    """Establishes a connection to the database and returns the connection object."""
    try:
        return psycopg2.connect(
            dbname=config.db_name,
            user=config.username,
            password=config.db_password,
            host=config.db_host,
            port=config.db_server_port
        )
    except psycopg2.DatabaseError as error:
        raise Exception(f"Error connecting to the database: {str(error)}")

def schema_exists(schema: str, config: CredentialsConfig) -> bool:
    """Returns True if a schema exists in the database."""
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s;", (schema,))
                res = cur.fetchone()
                return res is not None
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)

def create_schema(schema: str, config: CredentialsConfig):
    """Creates a new schema in the database."""
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                query = f'CREATE SCHEMA "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)
    
def add_postgis_extension(schema: str, config: CredentialsConfig):
    """Adds the PostGIS extension to the specified schema."""
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                query = f'CREATE EXTENSION postgis SCHEMA "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)

def  check_empty_or_nonexistent_tables(schema: str, config: CredentialsConfig) -> bool:
    """Return True, if tables (nodes, ways) are empty or non-existent."""
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                for t in TABLES:
                    query =  f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = '{schema}' AND table_name = '{t}');"
                    cur.execute(query)
                    exists = cur.fetchone()[0]
                    if exists:
                        query = f"SELECT EXISTS (SELECT  * FROM {schema}.{t} limit 1) as has_data;"
                        cur.execute(query)
                        has_data = cur.fetchone()[0]
                        if has_data: # table exists and isn't empty
                            return False
        return True
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)