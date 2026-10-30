import atexit
import logging
import os
import select
import socket
import threading
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple
from collections.abc import Iterable, Mapping, Sequence

import geopandas as gpd
import paramiko
import pandas as pd
import psycopg2
import psycopg2.errors
import psycopg2.sql
import sqlalchemy
from sqlalchemy.engine import Row
from tqdm import tqdm

from roadgraphtool.config import Config


SqlParams = Mapping[str, Any] | Sequence[Mapping[str, Any]]


class PostgresNoticeLogger:
    def append(self, notice):
        message = notice.strip()
        if message:
            logging.info("[postgres] %s", message)


def _parse_ssh_server(server: str) -> Tuple[str, int]:
    """host or host:port (IPv6 not supported). Default SSH port 22."""
    if ":" in server:
        host, port_s = server.rsplit(":", 1)
        if port_s.isdigit():
            return host, int(port_s)
    return server, 22


class _PumpEndpoint:
    """Socket-like endpoint plus a label for tunnel pump logging."""

    __slots__ = ("sock", "label", "_lock", "_write_closed", "_closed")

    def __init__(self, sock: Any, label: str) -> None:
        self.sock = sock
        self.label = label
        self._lock = threading.Lock()
        self._write_closed = False
        self._closed = False

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def recv(self, size: int) -> bytes:
        return self.sock.recv(size)

    def sendall(self, data: bytes) -> None:
        self.sock.sendall(data)

    def shutdown_write(self) -> None:
        with self._lock:
            if self._write_closed or self._closed:
                return
            self._write_closed = True

        try:
            if hasattr(self.sock, "shutdown_write"):
                self.sock.shutdown_write()
            elif hasattr(self.sock, "shutdown"):
                self.sock.shutdown(socket.SHUT_WR)
        except Exception:
            logging.debug("Endpoint write side already shut down (endpoint=%s)", self.label, exc_info=True)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._write_closed = True

        try:
            if hasattr(self.sock, "shutdown") and not hasattr(self.sock, "shutdown_write"):
                self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            logging.debug("Endpoint already shut down (endpoint=%s)", self.label, exc_info=True)

        try:
            self.sock.close()
        except Exception:
            logging.debug("Endpoint already closed (endpoint=%s)", self.label, exc_info=True)


class _PumpConnection:
    """Coordinates half-close and final close for the two pump directions."""

    __slots__ = ("local", "remote", "_lock", "_finished")

    def __init__(self, local: _PumpEndpoint, remote: _PumpEndpoint) -> None:
        self.local = local
        self.remote = remote
        self._lock = threading.Lock()
        self._finished = 0

    def finish_direction(self, dst: _PumpEndpoint) -> None:
        dst.shutdown_write()

        close_all = False
        with self._lock:
            self._finished += 1
            close_all = self._finished >= 2

        if close_all:
            self.local.close()
            self.remote.close()


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

    def _pump(self, src: _PumpEndpoint, dst: _PumpEndpoint, connection: _PumpConnection) -> None:
        try:
            while True:
                try:
                    data = src.recv(65536)
                except socket.timeout:
                    if src.is_closed:
                        logging.debug("Pump stopped after endpoint closed (endpoint=%s)", src.label)
                        break
                    continue
                except (OSError, EOFError):
                    if src.is_closed:
                        logging.debug("Pump stopped after endpoint closed (endpoint=%s)", src.label)
                    else:
                        logging.exception("Error in _pump on recv (endpoint=%s)", src.label)
                    break
                if not data:
                    break
                try:
                    dst.sendall(data)
                except (OSError, EOFError):
                    if dst.is_closed:
                        logging.debug("Pump stopped after destination closed (endpoint=%s)", dst.label)
                    else:
                        logging.exception("Error in _pump on sendall (endpoint=%s)", dst.label)
                    break
        finally:
            connection.finish_direction(dst)

    def _handle_client(self, client_sock: socket.socket) -> None:
        try:
            transport = self._ssh_client.get_transport()
            if transport is None or not transport.is_active():
                return
            channel = transport.open_channel(
                "direct-tcpip",
                self._remote_bind_address,
                client_sock.getpeername(),
            )
            channel.settimeout(180)
        except Exception as e:
            logging.warning("SSH tunnel channel open failed: %s", e)
            try:
                client_sock.close()
            except OSError:
                logging.exception("Error in _handle_client when closing client socket")
            return

        local_endpoint = _PumpEndpoint(client_sock, "local")
        remote_endpoint = _PumpEndpoint(channel, "remote")
        connection = _PumpConnection(local_endpoint, remote_endpoint)

        t_up = threading.Thread(
            target=self._pump,
            args=(
                local_endpoint,
                remote_endpoint,
                connection,
            ),
            daemon=True,
        )
        t_down = threading.Thread(
            target=self._pump,
            args=(
                remote_endpoint,
                local_endpoint,
                connection,
            ),
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
                    logging.exception("Error in stop when closing listener socket")
                self._listener = None
            if self._accept_thread is not None:
                self._accept_thread.join(timeout=5.0)
                self._accept_thread = None
            if self._ssh_client is not None:
                try:
                    self._ssh_client.close()
                except Exception:
                    logging.exception("Error in stop when closing ssh client")
                self._ssh_client = None
            self._stop_event.clear()

    def restart(self) -> None:
        self.stop()
        self.start()


def ensure_db_connection(db_function):
    """
    Decorator for Database methods: verifies the database is initialized and re-establishes
    the SSH tunnel and the database connections if the tunnel has dropped.
    """

    def wrapper(*args, **kwargs):
        args[0]._ensure_connected()
        return db_function(*args, **kwargs)

    return wrapper


class Database(object):
    """
    Singleton for database connection.

    ``init_db(config)`` opens the SSH tunnel (when the ``ssh`` section is configured) and the
    database connections eagerly. Methods decorated with ``ensure_db_connection`` re-establish the
    tunnel and the connections if the tunnel has dropped in the meantime.

    Import as:

    from roadgraphtool.db import db

    Attributes:
        _sqlalchemy_engine: SQLAlchemy engine object
        _psycopg2_connection: psycopg2 connection object
        _ssh_server_connection: ParamikoTunnelForwarder when SSH is configured
        db_server_address: address of the database server. When SSH is configured, this is the local
        bind address of the tunnel.
        db_name: name of the database.
        db_server_port: port of the database server. When SSH is configured, this is the local bind
        port of the tunnel.
        schema: the schema holding the Road Graph Tool tables (root ``schema`` of the config). Every connection
        uses the search path ``<schema>, public``, so unqualified table names resolve to this schema, while the
        extensions (PostGIS, pgRouting, hstore) are found in ``public``.
    """

    def __init__(self) -> None:
        self.config: Config | None = None
        self.schema: str = "public"
        self.db_server_address: str | None = None
        self.db_server_port: int | None = None
        self.db_name: str | None = None
        self._ssh_server_connection: ParamikoTunnelForwarder | None = None
        self._psycopg2_connection = None
        self._sqlalchemy_engine: sqlalchemy.engine.Engine | None = None
        atexit.register(self._close_db_connections)

    @property
    def ssh_configured(self) -> bool:
        return self.config is not None and hasattr(self.config, "ssh")

    @property
    def ssh_tunnel_local_port(self) -> int:
        if self._ssh_server_connection is not None:
            return int(self._ssh_server_connection.local_bind_port)
        return int(self.db_server_port or 0)

    def initialize(self, config, schema: str = "public"):
        self.config = config
        self.schema = schema

        self.db_server_port = self.config.db_server_port
        self.db_name = self.config.db_name
        self.db_server_address = self.config.db_host

        if self.ssh_configured:
            self._start_ssh_tunnel()
        self._open_db_connections()

    def _open_db_connections(self):
        # psycopg2 connection object
        logging.info("Starting _psycopg2 connection")
        self._psycopg2_connection = self._get_new_psycopg2_connection()

        # SQLAlchemy init. SQLAlchemy is used by pandas and geopandas
        logging.info("Starting sql_alchemy connection")
        self._sqlalchemy_engine = sqlalchemy.create_engine(
            self._get_sql_alchemy_engine_url(),
            pool_pre_ping=True,
            connect_args={"options": self._connection_options()},
        )

    @staticmethod
    def search_path(schema: str) -> str:
        """SQL search path for *schema*: the schema itself, then ``public`` holding the extensions."""
        quoted = '"' + schema.replace('"', '""') + '"'
        return "public" if schema == "public" else f"{quoted}, public"

    def _connection_options(self) -> str:
        """libpq ``options`` setting the default search path of every new connection."""
        search_path = self.search_path(self.schema).replace(", ", ",")
        return "-c search_path=" + search_path.replace("\\", "\\\\").replace(" ", "\\ ")

    def _close_db_connections(self):
        if self._psycopg2_connection is not None:
            try:
                self._psycopg2_connection.close()
            except Exception:
                logging.debug("psycopg2 connection already closed", exc_info=True)
            self._psycopg2_connection = None
        if self._sqlalchemy_engine is not None:
            self._sqlalchemy_engine.dispose()
            self._sqlalchemy_engine = None

    def _start_ssh_tunnel(self):
        passphrase = None
        if hasattr(self.config.ssh, "private_key_passphrase"):
            passphrase = self.config.ssh.private_key_passphrase

        self._ssh_server_connection = ParamikoTunnelForwarder(
            ssh_server=self.config.ssh.server,
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

        self.db_server_address = self._ssh_server_connection.local_bind_address[0]
        self.db_server_port = self._ssh_server_connection.local_bind_port

    def _ensure_connected(self):
        """
        Raise if ``init_db`` was not called. When SSH is configured and the tunnel has dropped,
        restart it and recreate the database connections, which point at the dead tunnel sockets.
        """
        if self.config is None:
            raise RuntimeError("Database is not initialized. Call roadgraphtool.db.init_db(config) first.")
        if not self.ssh_configured:
            return

        tunnel = self._ssh_server_connection
        if tunnel.is_alive and tunnel.is_active:
            return

        logging.warning("SSH tunnel is down, reconnecting")
        tunnel.restart()
        self.db_server_address = tunnel.local_bind_address[0]
        self.db_server_port = tunnel.local_bind_port
        self._close_db_connections()
        self._open_db_connections()

    def _get_sql_alchemy_engine_url(self) -> sqlalchemy.engine.URL:
        # URL.create escapes special characters (e.g., '@' in the password)
        return sqlalchemy.engine.URL.create(
            'postgresql+psycopg2',
            username=self.config.username,
            password=self.config.db_password,
            host=self.db_server_address,
            port=self.db_server_port,
            database=self.db_name,
        )

    def _get_new_psycopg2_connection(self):
        """
        Handles creation of db connection.
        """
        try:
            return psycopg2.connect(
                user=self.config.username,
                password=self.config.db_password,
                host=self.db_server_address,
                port=self.db_server_port,
                dbname=self.db_name,
                options=self._connection_options(),
            )
        except psycopg2.OperationalError as er:
            logging.error(str(er))
            if self._ssh_server_connection is not None:
                logging.info("Tunnel status: %s", str(self._ssh_server_connection.tunnel_is_up))
            raise

    def _get_new_async_psycopg2_connection(self):
        try:
            return psycopg2.connect(
                user=self.config.username,
                password=self.config.db_password,
                host=self.db_server_address,
                port=self.db_server_port,
                dbname=self.db_name,
                options=self._connection_options(),
                async_=True,
            )
        except psycopg2.OperationalError as er:
            logging.error(str(er))
            if self._ssh_server_connection is not None:
                logging.info("Tunnel status: %s", str(self._ssh_server_connection.tunnel_is_up))
            raise

    @staticmethod
    def _wait_for_async_psycopg2_connection(connection) -> None:
        while True:
            state = connection.poll()
            if state == psycopg2.extensions.POLL_OK:
                return
            if state == psycopg2.extensions.POLL_READ:
                select.select([connection.fileno()], [], [])
                continue
            if state == psycopg2.extensions.POLL_WRITE:
                select.select([], [connection.fileno()], [])
                continue
            raise psycopg2.OperationalError(f"Unexpected psycopg2 poll state: {state}")

    @ensure_db_connection
    def get_new_cursor(self):
        return self._psycopg2_connection.cursor()

    @ensure_db_connection
    def commit(self):
        self._psycopg2_connection.commit()

    @ensure_db_connection
    def execute_sql(self, query: str, args: SqlParams | None = None, schema: str | None = None, use_transactions: bool=True) -> sqlalchemy.engine.cursor.CursorResult[Any]:
        """
        Execute SQL that doesn't return any value.

        *schema* defaults to the configured schema (``self.schema``).
        """
        if schema is None:
            schema = self.schema
        with self._sqlalchemy_engine.connect() as connection:
            if not use_transactions:
                connection.execution_options(isolation_level="AUTOCOMMIT")
            with connection.begin():
                connection.execute(sqlalchemy.text(f"SET search_path TO {self.search_path(schema)};"))
                result = connection.execute(sqlalchemy.text(query), args)
                connection.execute(sqlalchemy.text(f"SET search_path TO {self.search_path(self.schema)};"))
                return result

    @ensure_db_connection
    def execute_sql_and_fetch_all_rows(self, query, *args) -> list[Row]:
        with self._sqlalchemy_engine.begin() as conn:
            result = conn.execute(sqlalchemy.text(query), *args).all()
            return result

    @staticmethod
    def _call_arg_value_and_cast(spec: Any) -> Tuple[Optional[str], Any]:
        """
        Each argument is either a plain value (no cast, ``%s``), or ``(value, postgres_type)`` where
        *postgres_type* is a trusted SQL type fragment. A 2-tuple is treated as typed only when the
        second element is a string (to avoid breaking when a real tuple value is passed as a scalar).
        """
        if (
            isinstance(spec, tuple)
            and len(spec) == 2
            and isinstance(spec[1], str)
        ):
            return spec[1], spec[0]
        return None, spec

    @staticmethod
    def _compose_call_sql(
        procedure_name: str,
        arguments: tuple[Any, ...],
        *,
        named_arguments: Optional[Mapping[str, Any]],
    ) -> Tuple[Any, tuple[Any, ...]]:
        """
        Build CALL ... for psycopg2. Returns (sql_composable, params_tuple).
        *named_arguments* values follow the same rules as positional specs in *_call_arg_value_and_cast*.
        """
        if named_arguments is not None and len(arguments) > 0:
            raise ValueError("Pass either positional arguments or named_arguments, not both.")
        params: list[Any] = []
        arg_parts: list[Any] = []

        if named_arguments is not None:
            for pname, spec in named_arguments.items():
                cast, val = Database._call_arg_value_and_cast(spec)
                if cast:
                    arg_parts.append(
                        psycopg2.sql.Composed(
                            [
                                psycopg2.sql.Identifier(pname),
                                psycopg2.sql.SQL(" => CAST(%s AS "),
                                psycopg2.sql.SQL(cast),
                                psycopg2.sql.SQL(")"),
                            ]
                        )
                    )
                else:
                    arg_parts.append(
                        psycopg2.sql.Composed(
                            [
                                psycopg2.sql.Identifier(pname),
                                psycopg2.sql.SQL(" => %s"),
                            ]
                        )
                    )
                params.append(val)
        else:
            for spec in arguments:
                cast, val = Database._call_arg_value_and_cast(spec)
                if cast:
                    arg_parts.append(
                        psycopg2.sql.SQL("CAST(%s AS {})").format(psycopg2.sql.SQL(cast))
                    )
                else:
                    arg_parts.append(psycopg2.sql.SQL("%s"))
                params.append(val)

        inner = psycopg2.sql.SQL(", ").join(arg_parts)
        stmt = psycopg2.sql.SQL("CALL {} ({})").format(
            psycopg2.sql.Identifier(procedure_name),
            inner,
        )
        return stmt, tuple(params)

    @ensure_db_connection
    def execute_procedure(
        self,
        procedure_name: str,
        *arguments: Any,
        named_arguments: Optional[Mapping[str, Any]] = None,
        schema: str | None = None,
    ) -> None:
        """
        Execute a stored procedure (CALL) with psycopg2 so PostgreSQL notices are logged as they arrive.

        *schema* defaults to the configured schema (``self.schema``).

        Pass positional procedure arguments as varargs. Each argument is either a plain value (bound as
        ``%s`` with no cast), or ``(value, postgres_type)`` for ``CAST(%s AS type)``.

        Alternatively pass only ``named_arguments=``: a mapping from parameter name to the same kinds of
        values (plain or ``(value, postgres_type)``). Do not combine varargs with ``named_arguments``.
        """
        query, params = self._compose_call_sql(
            procedure_name,
            arguments,
            named_arguments=named_arguments,
        )
        connection = self._get_new_async_psycopg2_connection()
        transaction_started = False

        try:
            self._wait_for_async_psycopg2_connection(connection)
            old_notices = connection.notices
            connection.notices = PostgresNoticeLogger()

            cursor = connection.cursor()
            try:
                cursor.execute("BEGIN;")
                self._wait_for_async_psycopg2_connection(connection)
                transaction_started = True

                cursor.execute(f"SET search_path TO {self.search_path(schema or self.schema)};")
                self._wait_for_async_psycopg2_connection(connection)

                cursor.execute(query, params)
                self._wait_for_async_psycopg2_connection(connection)

                cursor.execute(f"SET search_path TO {self.search_path(self.schema)};")
                self._wait_for_async_psycopg2_connection(connection)

                cursor.execute("COMMIT;")
                self._wait_for_async_psycopg2_connection(connection)
                transaction_started = False
            except Exception:
                if transaction_started:
                    try:
                        cursor.execute("ROLLBACK;")
                        self._wait_for_async_psycopg2_connection(connection)
                    except Exception:
                        logging.exception("Failed to roll back async procedure transaction")
                raise
            finally:
                cursor.close()
                connection.notices = old_notices
        except Exception:
            raise
        finally:
            connection.close()

    @ensure_db_connection
    def execute_script(self, script_path: Path, schema: str = 'public', raise_on_error: bool = False):
        """Execute the SQL script in one transaction. On error, the transaction is rolled back and the error is
        logged, or raised if *raise_on_error*."""
        script = Path(script_path).read_text(encoding="utf-8")
        try:
            self.execute_statements([script], schema)
        except Exception as e:
            if raise_on_error:
                raise
            logging.error(f"Error executing script {script_path}: {e}")

    @ensure_db_connection
    def execute_statements(self, statements: Iterable[str], schema: str = 'public') -> None:
        """Execute the SQL *statements* (``{schema}`` replaced by *schema*) in one transaction. On error, the
        transaction is rolled back and the error is raised."""
        cursor = self._psycopg2_connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement.replace('{schema}', schema))
            self._psycopg2_connection.commit()
        except Exception:
            self._psycopg2_connection.rollback()
            raise
        finally:
            cursor.close()

    def set_schema(self, schema: str):
        """
        Set search path to schema
        """
        with self._sqlalchemy_engine.connect() as connection:
            with connection.begin():
                connection.execute(sqlalchemy.text(f"SET search_path TO {self.search_path(schema)};"))

    @ensure_db_connection
    def execute_query_to_geopandas(self, sql: str, schema: str | None = None, **kwargs) -> pd.DataFrame:
        """
        Execute sql and load the result to Pandas DataFrame

        *schema* defaults to the configured schema (``self.schema``).

        kwargs are the same as for the pd.read_sql_query(), notably
        index_col=None
        """
        with self._sqlalchemy_engine.connect() as connection:
            connection.execute(sqlalchemy.text(f"SET search_path TO {self.search_path(schema or self.schema)};"))
            return gpd.read_postgis(sql, connection, **kwargs)

    @ensure_db_connection
    def execute_count_query(self, query: str) -> int:
        data = self.execute_sql_and_fetch_all_rows(query)
        return data[0][0]

    @ensure_db_connection
    def drop_table_if_exists(self, table_name: str) -> None:
        drop_sql = f"DROP TABLE IF EXISTS {table_name}"
        self.execute_sql(drop_sql)

    @ensure_db_connection
    def execute_query_to_pandas(self, sql: str, **kwargs) -> pd.DataFrame:
        """
        Execute sql and load the result to Pandas DataFrame

        kwargs are the same as for the pd.read_sql_query(), notably
        index_col=None
        """
        data = pd.read_sql_query(sql, self._sqlalchemy_engine, **kwargs)
        return data

    @ensure_db_connection
    def dataframe_to_db_table(
        self,
        df: pd.DataFrame,
        table_name: str,
        chunk: bool = True,
        chunk_size: int = 10_000,
        **kwargs
    ) -> None:
        """
        Save DataFrame to a new table in the database

        the dataframe method cannot accept psycopg2 connection, only SQLAlchemy
        connections or connection strings.

        https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_sql.html
        """
        if type(df) is gpd.GeoDataFrame:
            raise ValueError("dataframe_to_db_table function does not support GeoDataFrames. Use geodataframe_to_db_table instead.")

        if 'index' not in kwargs:
            kwargs['index'] = False
        kwargs.setdefault('schema', self.schema)

        if not chunk:
            df.to_sql(
                table_name,
                con=self._sqlalchemy_engine,
                if_exists='append',
                **kwargs,
            )
            return

        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1 when chunk=True")

        n = len(df)
        for start in tqdm(range(0, n, chunk_size), desc=f"to_sql {table_name}"):
            part = df.iloc[start : start + chunk_size]
            part.to_sql(
                table_name,
                con=self._sqlalchemy_engine,
                # chunksize=chunk_size,
                if_exists='append',
                **kwargs,
            )

    @ensure_db_connection
    def geodataframe_to_db_table(
        self,
        gdf: gpd.GeoDataFrame,
        table_name: str,
        store_index: bool = True,
        data_types: dict = None,
        chunk: bool = True,
        chunk_size: int = 5_000,
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

        # GeoPandas writes to `public` when no schema is given, ignoring the search path
        kwargs.setdefault('schema', self.schema)

        if not chunk:
            gdf.to_postgis(
                table_name,
                con=self._sqlalchemy_engine,
                if_exists='append',
                index=store_index,
                dtype=data_types,
                **kwargs,
            )
            return

        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1 when chunk=True")

        n = len(gdf)
        for start in tqdm(range(0, n, chunk_size), desc=f"to_postgis {table_name}"):
            part = gdf.iloc[start : start + chunk_size]
            part.to_postgis(
                table_name,
                con=self._sqlalchemy_engine,
                if_exists='append',
                index=store_index,
                dtype=data_types,
                **kwargs,
            )

    @ensure_db_connection
    def db_table_to_pandas(self, table_name: str, **kwargs) -> pd.DataFrame:
        return pd.read_sql_table(table_name, con=self._sqlalchemy_engine, **kwargs)

    @ensure_db_connection
    def create_schema(self, schema_name: str) -> None:
        """
        Create a new schema.
        """
        create_schema_sql = f"CREATE SCHEMA IF NOT EXISTS {schema_name};"
        self.execute_sql(create_schema_sql)

    @ensure_db_connection
    def drop_schema(self, schema_name: str, cascade: bool = False) -> None:
        """
        Drop a schema.
        If cascade is True, will drop all objects in the schema.
        """
        drop_schema_sql = f"DROP SCHEMA IF EXISTS {schema_name} {'CASCADE' if cascade else ''};"
        self.execute_sql(drop_schema_sql)

    @ensure_db_connection
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

    @ensure_db_connection
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

def init_db(config: Config):
    global db
    db.initialize(config.db, schema=getattr(config, "schema", "public"))
