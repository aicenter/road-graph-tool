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
init_db(config)
set_logging(config)

sql_dir = Path(__file__).parent.parent.parent / "SQL"
install_sql(config=config, db=db, sql_dir=sql_dir, include_tests=True)
