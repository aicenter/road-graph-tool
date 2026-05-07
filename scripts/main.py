import logging
import sys

from pathlib import Path
from roadgraphtool.config import parse_config_file, set_logging
import roadgraphtool.db
import roadgraphtool.pipeline


def main():
    args = sys.argv

    if len(args) < 2:
        logging.error("You have to provide a path to the config file as an argument.")
        return -1

    config = parse_config_file(Path(args[1]))
    set_logging(config)

    roadgraphtool.db.init_db(config)
    roadgraphtool.db.db._start_or_restart_ssh_connection_if_needed()

    roadgraphtool.pipeline.main(config)


if __name__ == '__main__':
    main()
