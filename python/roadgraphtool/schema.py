from typing import Optional, TYPE_CHECKING
import psycopg2
from roadgraphtool.credentials_config import CredentialsConfig

if TYPE_CHECKING:
    from psycopg2 import connection

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