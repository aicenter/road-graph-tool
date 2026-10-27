import logging
from pathlib import Path
import sys

from roadgraphtool.config import parse_config_file, set_logging
from roadgraphtool.db import db, init_db
from roadgraphtool.sql_install import install_sql

args = sys.argv
if len(args) < 2:
    logging.error("You have to provide a path to the config file as an argument.")
    exit(-1)

config = parse_config_file(Path(args[1]))
set_logging(config)
init_db(config)

install_sql(config=config, db=db, include_tests=True)
