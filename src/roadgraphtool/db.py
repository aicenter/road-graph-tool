import atexit
import logging
import os
import socket
import threading
from pathlib import Path
from typing import Optional, Tuple

import geopandas as gpd
import paramiko
import pandas as pd
import psycopg2
import psycopg2.errors
import sqlalchemy
from sqlalchemy.engine import Row


def _parse_ssh_server(server: str) -> Tuple[str, int]:
    """host or host:port (IPv6 not supported). Default SSH port 22."""
    if ":" in server:
        host, port_s = server.rsplit(":", 1)
        if port_s.isdigit():
            return host, int(port_s)
    return server, 22


class ParamikoTunnelForwarder:
    """
    Local TCP listen -> SSH direct-tcpip -> remote (host, port).
    Subset of behavior previously provided by sshtunnel.SSHTunnelForwarder.
    *key_filename* must be a resolved ``Path`` (e.g. from ``expand_relative_paths``).
    """

    def __init__(
        self,
        ssh_server: str,
        ssh_username: str,
        key_filename: Path,
        local_bind_address: Tuple[str, int],
        remote_bind_address: Tuple[str, int],
        passphrase: Optional[str] = None,
    ):
        self.ssh_host = ssh_server
        self._ssh_hostname, self._ssh_port = _parse_ssh_server(ssh_server)
        self._ssh_username = ssh_username
        self._key_path = key_filename
        self._passphrase = passphrase
        self._local_bind_requested = local_bind_address
        self._remote_bind_address = remote_bind_address

        self._ssh_client: Optional[paramiko.SSHClient] = None
        self._listener: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._local_bind_address: Tuple[str, int] = ("", 0)
        self._atexit_registered = False

    @property
    def local_bind_address(self) -> Tuple[str, int]:
        return self._local_bind_address

    @property
    def local_bind_port(self) -> int:
        return int(self._local_bind_address[1])

    @property
    def tunnel_is_up(self) -> dict:
        if self._listener is None:
            return {}
        return {self._local_bind_address: self._remote_bind_address}

    @property
    def is_alive(self) -> bool:
        return self._accept_thread is not None and self._accept_thread.is_alive()

    @property
    def is_active(self) -> bool:
        if not self.is_alive or self._ssh_client is None:
            return False
        try:
            t = self._ssh_client.get_transport()
            return t is not None and t.is_active()
        except Exception:
            return False

    def _connect_ssh(self) -> None:
        self._ssh_client = paramiko.SSHClient()
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        common = dict(
            hostname=self._ssh_hostname,
            port=self._ssh_port,
            username=self._ssh_username,
            key_filename=os.fspath(self._key_path),
            look_for_keys=False,
        )
        if self._passphrase is not None:
            common["passphrase"] = self._passphrase
        try:
            self._ssh_client.connect(**common, allow_agent=True)
        except paramiko.SSHException as e:
            logging.warning("paramiko.SSHException (retrying with allow_agent=False): %s", e)
            self._ssh_client.close()
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh_client.connect(**common, allow_agent=False)

    def _pump(self, src, dst) -> None:
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except (OSError, EOFError):
            pass
        finally:
            for s in (src, dst):
                try:
                    if hasattr(s, "shutdown"):
                        s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    s.close()
                except OSError:
                    pass

    def _handle_client(self, client_sock: socket.socket) -> None:
        try:
            transport = self._ssh_client.get_transport()
            if transport is None or not transport.is_active():
                return
            chan = transport.open_channel(
                "direct-tcpip",
                self._remote_bind_address,
                client_sock.getpeername(),
            )
        except Exception as e:
            logging.warning("SSH tunnel channel open failed: %s", e)
            try:
                client_sock.close()
            except OSError:
                pass
            return

        t_up = threading.Thread(
            target=self._pump,
            args=(client_sock, chan),
            daemon=True,
        )
        t_down = threading.Thread(
            target=self._pump,
            args=(chan, client_sock),
            daemon=True,
        )
        t_up.start()
        t_down.start()
        t_up.join()
        t_down.join()

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while not self._stop_event.is_set():
            self._listener.settimeout(0.5)
            try:
                client_sock, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_client,
                args=(client_sock,),
                daemon=True,
            ).start()

    def start(self) -> None:
        with self._lock:
            self._stop_event.clear()
            self._connect_ssh()

            self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(self._local_bind_requested)
            self._listener.listen(128)
            self._local_bind_address = self._listener.getsockname()

            self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._accept_thread.start()

            if not self._atexit_registered:
                atexit.register(self.stop)
                self._atexit_registered = True

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            if self._listener is not None:
                try:
                    self._listener.close()
                except OSError:
                    pass
                self._listener = None
            if self._accept_thread is not None:
                self._accept_thread.join(timeout=5.0)
                self._accept_thread = None
            if self._ssh_client is not None:
                try:
                    self._ssh_client.close()
                except Exception:
                    pass
                self._ssh_client = None
            self._stop_event.clear()

    def restart(self) -> None:
        self.stop()
        self.start()


def connect_db_if_required(db_function):
    """
    Check and reset ssh connection decorator for methods working with the db
    """

    def wrapper(*args, **kwargs):
        db = args[0]
        if not hasattr(db, '_initialized'):
            raise RuntimeError("Database is not initialized. Call roadgraphtool.db.init_db(config) first.")
        if hasattr(db, 'ssh_server_address'):
            db._start_or_restart_ssh_connection_if_needed()
        if not hasattr(db, '_db_connected'):
            db._set_up_db_connections()
        return db_function(*args, **kwargs)

    return wrapper


class Database(object):
    """
    Singleton for database connection.

    Connection only happens when it is required.

    Import as:
    
    from db import db

    Attributes:
        _sqlalchemy_engine: SQLAlchemy engine object
        _psycopg2_connection: psycopg2 connection object
        _ssh_server_connection: ParamikoTunnelForwarder when SSH is configured
        db_server_address: address of the database server. If ssh_server_address is specified, this address is 
        interpreted as a relative address to the ssh_server_address. 
        db_name: name of the database.
        db_server_port: port of the database server. 
        ssh_server_address: address of the ssh server.
    """

    config: dict

    db_server_address: str
    db_name: str
    db_server_port: int

    ssh_server_address: str

    _initialized: bool
    _db_connected: bool
    _sqlalchemy_engine: sqlalchemy.engine.Engine
    # _psycopg2_connection: psycopg2.connection.Connection
    _ssh_server_connection: ParamikoTunnelForwarder

    @property
    def ssh_tunnel_local_port(self) -> int:
        if getattr(self, "_ssh_server_connection", None) is not None:
            return int(self._ssh_server_connection.local_bind_port)
        return int(getattr(self, "db_server_port", 0))

    def initialize(self, config):
        self.config = config
        
        self.db_server_port = self.config.db_server_port
        self.db_name = self.config.db_name
        self.db_server_address = self.config.db_host

        if hasattr(self.config, 'ssh'):
            self.ssh_server_address = self.config.ssh.server
            
        self._initialized = True

    def _set_up_db_connections(self):
        # psycopg2 connection object
        logging.info("Starting _psycopg2 connection")
        self._psycopg2_connection = self._get_new_psycopg2_connection()

        # SQLAlchemy init. SQLAlchemy is used by pandas and geopandas
        logging.info("Starting sql_alchemy connection")
        sql_alchemy_engine_str = self._get_sql_alchemy_engine_str()
        self._sqlalchemy_engine = sqlalchemy.create_engine(sql_alchemy_engine_str)
        self._db_connected = True

    def _start_ssh_connection(self):
        passphrase = None
        if hasattr(self.config.ssh, "private_key_passphrase"):
            passphrase = self.config.ssh.private_key_passphrase

        self._ssh_server_connection = ParamikoTunnelForwarder(
            ssh_server=self.ssh_server_address,
            ssh_username=self.config.ssh.server_username,
            key_filename=self.config.ssh.private_key_path,
            local_bind_address=("localhost", int(self.config.ssh.tunnel_port)),
            remote_bind_address=("localhost", int(self.config.db_server_port)),
            passphrase=passphrase,
        )
        self._ssh_server_connection.start()
        logging.info(
            "SSH tunnel established from %s to %s/%s",
            self._ssh_server_connection.local_bind_address,
            self._ssh_server_connection.ssh_host,
            self.config.db_server_port,
        )

        self.db_server_port = self._ssh_server_connection.local_bind_port

    def _start_or_restart_ssh_connection_if_needed(self):
        """
        Set up or reset ssh tunnel.
        """

        if not hasattr(self, '_ssh_server_connection'):
            # INITIALIZATION
            logging.info("Connecting to ssh server")
            self._start_ssh_connection()
        else:
            # RESET
            if not self._ssh_server_connection.is_alive or not self._ssh_server_connection.is_active:
                self._ssh_server_connection.restart()

    def _get_sql_alchemy_engine_str(self):
        sql_alchemy_engine_str = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'.format(
            user=self.config.username,
            password=self.config.db_password,
            host=self.db_server_address,
            port=self.db_server_port,
            dbname=self.db_name)

        return sql_alchemy_engine_str

    def _get_new_psycopg2_connection(self):
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
            if getattr(self, "_ssh_server_connection", None) is not None:
                logging.info("Tunnel status: %s", str(self._ssh_server_connection.tunnel_is_up))
            raise

    @connect_db_if_required
    def get_new_cursor(self):
        return self._psycopg2_connection.cursor()

    @connect_db_if_required
    def commit(self):
        self._psycopg2_connection.commit()

    @connect_db_if_required
    def execute_sql(self, query, *args, schema='public', use_transactions=True) -> sqlalchemy.engine.Result:
        """
        Execute SQL that doesn't return any value.
        """
        with self._sqlalchemy_engine.connect() as connection:
            if not use_transactions:
                connection.execution_options(isolation_level="AUTOCOMMIT")
            with connection.begin():
                connection.execute(sqlalchemy.text(f"SET search_path TO {schema};"))
                result = connection.execute(sqlalchemy.text(query), *args)
                connection.execute(sqlalchemy.text(f"SET search_path TO public;"))
                return result

    @connect_db_if_required
    def execute_sql_and_fetch_all_rows(self, query, *args) -> list[Row]:
        with self._sqlalchemy_engine.begin() as conn:
            result = conn.execute(sqlalchemy.text(query), *args).all()
            return result

    @connect_db_if_required
    def execute_script(self, script_path: Path, schema: str = 'public'):
        with open(script_path) as f:
            script = f.read().replace('{schema}', schema)
            cursor = self._psycopg2_connection.cursor()
            try:
                cursor.execute(script)
                self._psycopg2_connection.commit()
            except Exception as e:
                logging.error(f"Error executing script {script_path}: {e}")
                self._psycopg2_connection.rollback()
            finally:
                cursor.close()

    def set_schema(self, schema: str):
        """
        Set search path to schema
        """
        with self._sqlalchemy_engine.connect() as connection:
            with connection.begin():
                connection.execute(sqlalchemy.text(f"SET search_path TO {schema};"))

    @connect_db_if_required
    def execute_query_to_geopandas(self, sql: str, schema='public', **kwargs) -> pd.DataFrame:
        """
        Execute sql and load the result to Pandas DataFrame

        kwargs are the same as for the pd.read_sql_query(), notably
        index_col=None
        """
        self.set_schema(schema)
        data = gpd.read_postgis(sql, self._sqlalchemy_engine, **kwargs)
        self.set_schema('public')
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
        if type(df) is gpd.GeoDataFrame:
            raise ValueError("dataframe_to_db_table function does not support GeoDataFrames. Use geodataframe_to_db_table instead.")

        df.to_sql(table_name, con=self._sqlalchemy_engine, if_exists='append', index=False)

    @connect_db_if_required
    def geodataframe_to_db_table(
        self,
        gdf: gpd.GeoDataFrame,
        table_name: str,
        store_index: bool = True,
        data_types: dict = None,
        **kwargs
    ) -> None:
        # if srid is None:
        #     srid = self.config.srid
        #
        # # set dataframe srid
        # gdf.set_crs(epsg=srid, inplace=True)

        if gdf.active_geometry_name is None or gdf.active_geometry_name not in gdf.columns:
            raise ValueError("the geodataframe_to_db_table function requires a the GeoDataFrame to have an active geometry column")

        if data_types is None:
            data_types = {}

        gdf.to_postgis(table_name, con=self._sqlalchemy_engine, if_exists='append', index=store_index, dtype=data_types)

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
db = Database()

def init_db(config):
    global db
    db.initialize(config.db)
