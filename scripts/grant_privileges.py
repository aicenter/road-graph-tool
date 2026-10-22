import argparse
from pathlib import Path

from roadgraphtool.config import parse_config_file, set_logging
from roadgraphtool.db import init_db
from roadgraphtool.privileges import grant_privileges

parser = argparse.ArgumentParser(
    description="Grant a role the privileges needed to work with Road Graph Tool: read the road network in the "
                "schema of the config, and create new schemas for processing road networks."
)
parser.add_argument("config", type=Path, help="path to the YAML config file with the connection of a user that can grant the privileges")
parser.add_argument("role", help="existing role that receives the privileges")
args = parser.parse_args()

config = parse_config_file(args.config)
set_logging(config)
init_db(config)

grant_privileges(db_name=config.db.db_name, role=args.role, schema=config.schema)
