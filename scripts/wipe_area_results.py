import sys
import logging
from pathlib import Path

from roadgraphtool.config import parse_config_file, set_logging
import roadgraphtool.db

args = sys.argv
if len(args) < 2:
    logging.error("You have to provide a path to the road-graph-tool YAML config file as an argument.")
    sys.exit(1)
config_path = Path(args[1])

config = parse_config_file(config_path)
set_logging(config)

roadgraphtool.db.init_db(config)

# wipes the edges and strong components of the configured area (root `area_id` of the config) in the configured schema
# (root `schema` of the config), so that the graph in the area can be contracted again
roadgraphtool.db.db.execute_procedure("wipe_area_results", (config.area_id, "smallint"))
