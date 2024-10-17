import configparser
import logging
import os
import pathlib
import subprocess
import stat


def read_config(config_paths):
    """
    Read database credentials from .ini file.
    """
    config = configparser.ConfigParser()

    read_configs = config.read(config_paths)
    if read_configs:
        logging.info("Successfully read db config from: {}".format(str(read_configs)))
    else:
        logging.error(
            "Failed to find any config in {}".format(
                [os.path.abspath(path) for path in config_paths]
            )
        )
    return config


class CredentialsConfig:
    PROJECT_PATH = pathlib.Path(__file__).parent.parent.parent
    PGPASS_PATH = str(PROJECT_PATH / "pgpass.conf")
    CONFIG_PATHS = [str(PROJECT_PATH / "config.ini")]

    def __init__(self):
        config = read_config(self.CONFIG_PATHS)

        database = config["database"]

        self.db_server_port = int(database.get("db_server_port", "5432"))
        self.username = database.get("username", None)
        self.db_password = database.get("db_password", "")
        self.db_host = database.get("db_host", "localhost")
        self.db_name = database.get("db_name", None)

        if "ssh" in config:
            ssh = config["ssh"]
            self.server_username = ssh.get("server_username", None)
            self.private_key_path = ssh.get("private_key_path", None)
            self.private_key_phrase = ssh.get("private_key_passphrase", None)
            self.host = ssh.get("host", "localhost")
            self.server = ssh.get("server", None)

        if "username" not in database or "db_name" not in database:
            raise RuntimeError(
                'Database critical credentials ("username" or/and "db_name") not found in config file. Parsed credentials are:\n{}'.format(
                    self
                )
            )
        
        self._setup_pgpass()

    def __str__(self):
        return "\n".join(
            [
                "Database credentials:",
                "   db_server_port: {}".format(self.db_server_port),
                "   username: {}".format(self.username),
                "   db_password: {}".format(self.db_password),
                "   db_host: {}".format(self.db_host),
                "   db_name: {}".format(self.db_name),
                "SSH credentials:",
                "   server_username: {}".format(self.server_username),
                "   private_key_path: {}".format(self.private_key_path),
                "   private_key_phrase: {}".format(self.private_key_phrase),
                "   host: {}".format(self.host),
                "   server: {}".format(self.server),
            ]
        )
    
    def _setup_pgpass(self):
        """Create pgpass file or rewrite its content."""
        # hostname:port:database:username:password
        content = f"{self.db_host}:{self.db_server_port}:{self.db_name}:{self.username}:{self.db_password}"
        with open(self.PGPASS_PATH, 'w') as pgfile:
            pgfile.write(content)
        os.chmod(self.PGPASS_PATH, stat.S_IRUSR | stat.S_IWUSR)
        os.environ['PGPASSFILE'] = self.PGPASS_PATH



CREDENTIALS = CredentialsConfig()
