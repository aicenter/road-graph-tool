import atexit
import logging
import psycopg2
import sshtunnel
import sqlalchemy
import pandas as pd
import psycopg2.errors
import geopandas as gpd
from pathlib import Path
from sqlalchemy.engine import Row

from roadgraphtool.credentials_config import CREDENTIALS

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')


def connect_db_if_required(db_function):
    """
    Check and reset ssh connection decorator for methods working with the db
    """

    def wrapper(*args, **kwargs):
        db = args[0]
        if hasattr(db, 'server'):
            db.start_or_restart_ssh_connection_if_needed()
        if not db.is_connected():
            db.set_up_db_connections()
        return db_function(*args, **kwargs)

    return wrapper


class __Database:
    """
    To be used as singleton instance db.

    Connection only happens when it is required.

    Import as:
    from db import db
    """
    config = CREDENTIALS

    def __init__(self):
        # If private key specified, assume ssh connection and try to set it up
        self.db_server_port = self.config.db_server_port
        self.db_name = self.config.db_name
        self.ssh_tunnel_local_port = 1113
        if hasattr(self.config, 'server'):
            self.server = self.config.server
            self.ssh_server = None
            self.host = self.config.host
        else:
            self.host = self.config.db_host

        self._sqlalchemy_engine = None
        self._psycopg2_connection = None
        self._sql_alchemy_engine_str = None

    def is_connected(self):
        return (self._psycopg2_connection is not None) and (self._sqlalchemy_engine is not None)

    def set_up_db_connections(self):
        # psycopg2 connection object
        logging.info("Starting _psycopg2 connection")
        self._psycopg2_connection = self.get_new_psycopg2_connection()

        # SQLAlchemy init. SQLAlchemy is used by pandas and geopandas
        logging.info("Starting sql_alchemy connection")
        self._sql_alchemy_engine_str = self.get_sql_alchemy_engine_str()
        self._sqlalchemy_engine = sqlalchemy.create_engine(self._sql_alchemy_engine_str)

    def set_ssh_to_db_server_and_set_port(self):
        ssh_kwargs = dict(
            ssh_pkey=self.config.private_key_path,
            ssh_username=self.config.server_username,
            ssh_private_key_password=self.config.private_key_phrase,
            remote_bind_address=('localhost', self.db_server_port),
            local_bind_address=('localhost', self.ssh_tunnel_local_port)
        )
        try:
            self.ssh_server = sshtunnel.open_tunnel(self.server, **ssh_kwargs)
        except sshtunnel.paramiko.SSHException as e:
            # sshtunnel dependency paramiko may attempt to use ssh-agent and crashes if it fails
            logging.warning(f"sshtunnel.paramiko.SSHException: '{e}'")
            self.ssh_server = sshtunnel.open_tunnel(self.server, **ssh_kwargs, allow_agent=False)

        self.ssh_server.start()
        logging.info(
            "SSH tunnel established from %s to %s/%s",
            self.ssh_server.local_bind_address,
            self.ssh_server.ssh_host,
            self.db_server_port
        )

        self.db_server_port = self.ssh_server.local_bind_port

    def start_or_restart_ssh_connection_if_needed(self):
        """
        Set up or reset ssh tunnel.
        """
        if self.config.private_key_path is not None:
            if self.ssh_server is None:
                # INITIALIZATION
                logging.info("Connecting to ssh server")
                self.set_ssh_to_db_server_and_set_port()
            else:
                # RESET
                if not self.ssh_server.is_alive or not self.ssh_server.is_active:
                    self.ssh_server.restart()

    def get_sql_alchemy_engine_str(self):
        sql_alchemy_engine_str = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'.format(
            user=self.config.username,
            password=self.config.db_password,
            host=self.host,
            port=self.db_server_port,
            dbname=self.db_name)

        return sql_alchemy_engine_str

    def get_new_psycopg2_connection(self):
        """
        Handles creation of db connection.
        """
        try:
            psycopg2_connection = psycopg2.connect(
                user=self.config.username,
                password=self.config.db_password,
                host=self.config.db_host,
                port=self.db_server_port,
                dbname=self.db_name
            )

            atexit.register(psycopg2_connection.close)
            return psycopg2_connection
        except psycopg2.OperationalError as er:
            logging.error(str(er))
            logging.info("Tunnel status: %s", str(self.ssh_server.tunnel_is_up))
            return None

    @connect_db_if_required
    def execute_sql(self, query, *args, schema='public', use_transactions=True) -> None:
        """
        Execute SQL that doesn't return any value.
        """
        with self._sqlalchemy_engine.connect() as connection:
            if not use_transactions:
                connection.execution_options(isolation_level="AUTOCOMMIT")
            with connection.begin():
                connection.execute(sqlalchemy.text(f"SET search_path TO {schema};"))
                connection.execute(sqlalchemy.text(query), *args)
                connection.execute(sqlalchemy.text(f"SET search_path TO public;"))

    @connect_db_if_required
    def execute_sql_and_fetch_all_rows(self, query, *args) -> list[Row]:
        with self._sqlalchemy_engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(query), *args).all()
            return result

    @connect_db_if_required
    def execute_script(self, script_path: Path):
        with open(script_path) as f:
            script = f.read()
            cursor = self._psycopg2_connection.cursor()
            try:
                cursor.execute(script)
                self._psycopg2_connection.commit()
            except Exception as e:
                logging.error(f"Error executing script {script_path}: {e}")
                self._psycopg2_connection.rollback()
            finally:
                cursor.close()

    @connect_db_if_required
    def execute_query_to_geopandas(self, sql: str, **kwargs) -> pd.DataFrame:
        """
        Execute sql and load the result to Pandas DataFrame

        kwargs are the same as for the pd.read_sql_query(), notably
        index_col=None
        """
        data = gpd.read_postgis(sql, self._sqlalchemy_engine, **kwargs)
        return data

    @connect_db_if_required
    def execute_count_query(self, query: str) -> int:
        data = self.execute_sql_and_fetch_all_rows(query)
        return data[0][0]

    @connect_db_if_required
    def drop_table_if_exists(self, table_name: str) -> None:
        drop_sql = f"DROP TABLE IF EXISTS {table_name}"
        self.execute_sql(drop_sql)

    @connect_db_if_required
    def execute_query_to_pandas(self, sql: str, **kwargs) -> pd.DataFrame:
        """
        Execute sql and load the result to Pandas DataFrame

        kwargs are the same as for the pd.read_sql_query(), notably
        index_col=None
        """
        data = pd.read_sql_query(sql, self._sqlalchemy_engine, **kwargs)
        return data

    @connect_db_if_required
    def dataframe_to_db_table(self, df: pd.DataFrame, table_name: str, **kwargs) -> None:
        """
        Save DataFrame to a new table in the database

        the dataframe method cannot accept psycopg2 connection, only SQLAlchemy
        connections or connection strings.

        https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_sql.html
        """
        df.to_sql(table_name, con=self._sqlalchemy_engine, if_exists='append', index=False)

    @connect_db_if_required
    def db_table_to_pandas(self, table_name: str, **kwargs) -> pd.DataFrame:
        return pd.read_sql_table(table_name, con=self._sqlalchemy_engine, **kwargs)

    @connect_db_if_required
    def create_schema(self, schema_name: str) -> None:
        """
        Create a new schema.
        """
        create_schema_sql = f"CREATE SCHEMA IF NOT EXISTS {schema_name};"
        self.execute_sql(create_schema_sql)

    @connect_db_if_required
    def drop_schema(self, schema_name: str, cascade: bool = False) -> None:
        """
        Drop a schema.
        If cascade is True, will drop all objects in the schema.
        """
        drop_schema_sql = f"DROP SCHEMA IF EXISTS {schema_name} {'CASCADE' if cascade else ''};"
        self.execute_sql(drop_schema_sql)

    @connect_db_if_required
    def copy_table_structure(self, table_name: str, main_schema: str, new_schema: str) -> None:
        """
        Copy the table structure and dependencies (without data) from the main schema to the new schema.
        """
        table_exists_query = f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = '{new_schema.lower()}' 
                AND table_name = '{table_name.lower()}'
            );
        """
        table_exists = self.execute_sql_and_fetch_all_rows(table_exists_query)[0][0]

        if not table_exists:
            copy_sql = f"""
                CREATE TABLE {new_schema}.{table_name} (LIKE {main_schema}.{table_name} INCLUDING ALL);
            """
            self.execute_sql(copy_sql)
        else:
            logging.info(f"Table {table_name} already exists in schema {new_schema}. Skipping creation.")

    @connect_db_if_required
    def copy_all_tables_to_new_schema(self, main_schema: str, new_schema: str) -> None:
        """
        Copy all table structures (without data) from the main schema to the new schema.
        """
        tables_query = f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = '{main_schema}' AND table_type = 'BASE TABLE';
        """
        tables = self.execute_sql_and_fetch_all_rows(tables_query)

        for table in tables:
            table_name = table[0]
            self.copy_table_structure(table_name, main_schema, new_schema)


# db singleton
db = __Database()
