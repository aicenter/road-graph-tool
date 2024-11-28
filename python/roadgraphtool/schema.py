from typing import Optional, TYPE_CHECKING
import psycopg2

from roadgraphtool.credentials_config import CREDENTIALS
from roadgraphtool.log import LOGGER
from roadgraphtool.db import db

if TYPE_CHECKING:
    from psycopg2 import connection

TABLES = ["nodes", "ways"]

logger = LOGGER.get_logger('schema')

def get_connection() -> Optional['connection']:
    """Establishes a connection to the database and returns the connection object."""
    try:
        connection = psycopg2.connect(
            dbname=CREDENTIALS.db_name,
            user=CREDENTIALS.username,
            password=CREDENTIALS.db_password,
            host=CREDENTIALS.db_host,
            port=CREDENTIALS.db_server_port
        )
        return connection
    except psycopg2.DatabaseError as e:
        logger.error(f"Error connecting to the database: {str(e)}")
        raise

def setup_ssh_tunnel() -> int:
    """Set up SSH tunnel if needed and returns port number."""
    if hasattr(CREDENTIALS, "server") and CREDENTIALS.server is not None:  # remote connection
        db.start_or_restart_ssh_connection_if_needed()
        CREDENTIALS.db_server_port = db.ssh_tunnel_local_port
        return db.ssh_tunnel_local_port
    # local connection
    return CREDENTIALS.db_server_port

def connect_to_db_ssh() -> Optional['connection']:
    """Establishes an SSH tunnel and a connection to the database and returns the connection object."""
    setup_ssh_tunnel()
    return get_connection()

def setup_ssh_tunnel() -> int:
    """Set up SSH tunnel if needed and returns port number."""
    if hasattr(CREDENTIALS, "server") and CREDENTIALS.server is not None:  # remote connection
        db.start_or_restart_ssh_connection_if_needed()
        CREDENTIALS.db_server_port = db.ssh_tunnel_local_port
        return db.ssh_tunnel_local_port
    # local connection
    return CREDENTIALS.db_server_port

def connect_to_db_ssh() -> Optional['connection']:
    """Establishes an SSH tunnel and a connection to the database and returns the connection object."""
    setup_ssh_tunnel()
    return get_connection()

def create_schema(schema: str):
    """Creates a new schema in the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                query = f'CREATE SCHEMA if not exists "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as e:
        logger.error(f"Error with database: {str(e)}")
        raise
    
def add_postgis_extension(schema: str):
    """Adds the PostGIS extension to the specified schema."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                query = f'CREATE EXTENSION if not exists postgis SCHEMA "{schema}";'
                cur.execute(query)
    except (psycopg2.DatabaseError, Exception) as e:
        logger.error(f"Error with database: {str(e)}")
        raise

def check_empty_or_nonexistent_tables(schema: str, tables: list = TABLES) -> bool:
    """Returns True, if all tables from TABLES are non-existent or empty. 
    Returns False if at least one isn't empty."""
    try:
        with get_connection() as conn:
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
    except (psycopg2.DatabaseError, Exception) as e:
        logger.error(f"Error with database: {str(e)}")
        raise
