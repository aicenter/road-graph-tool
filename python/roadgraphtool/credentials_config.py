import configparser
import logging
import os
import pathlib


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
    CONFIG_PATHS = [f"{pathlib.Path(__file__).parent}/config.ini"]

    def __init__(self):
        config = read_config(self.CONFIG_PATHS)

        database = config["database"]

        if (
            "username" not in database
            or "db_host" not in database
            or "db_name" not in database
        ):
            raise Exception(
                'Either "username", "db_host" or "db_name" is missing from config.ini!'
            )

        self.db_server_port = int(database.get("db_server_port", "5432"))
        self.username = database["username"]
        self.db_password = database.get("db_password", "")
        self.db_host = database["db_host"]
        self.db_name = database["db_name"]

        if "ssh" in config:
            self.server_username = config["ssh"].get("server_username", None)
            self.private_key_path = config["ssh"].get("private_key_path", None)
            self.private_key_phrase = config["ssh"].get("private_key_passphrase", None)
            self.host = config["ssh"].get("host", "localhost")
            self.server = config["ssh"].get("server", None)


CREDENTIALS = CredentialsConfig()
