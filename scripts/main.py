import argparse
import json
import logging
import sys
from typing import Optional

from pathlib import Path
from roadgraphtool.config import parse_config_file, set_logging
import roadgraphtool.db
from roadgraphtool.db import db
from roadgraphtool.process_osm import import_osm_to_db
import roadgraphtool.overpass_import
import roadgraphtool.insert_area
import roadgraphtool.export
import roadgraphtool.distance_matrix_generator
from roadgraphtool.exceptions import MissingInputError
import roadgraphtool.pipeline


def configure_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="File containing the main flow of your application"
    )
    parser.add_argument(
        "-a", "--area_id", type=int, help="Id of the area.", required=True
    )
    parser.add_argument(
        "-s",
        "--area_srid",
        type=int,
        help="Postgis srid. Default is set to 4326.",
        default=4326,
        required=False,
    )
    parser.add_argument(
        "-f",
        "--fill-speed",
        type=bool,
        choices=[True, False],
        help="An option indicating if specific functions should process speed data. Default is set to False.",
        default=False,
        required=False,
    )
    parser.add_argument(
        '-i',
        '--import',
        dest='importing',
        action="store_true",
        help='Import OSM data to database specified in config.ini'
    )
    parser.add_argument(
        '-if',
        '--input-file',
        dest='input_file',
        required=True,
        help='Input OSM file path for -i/--import.'
    )
    parser.add_argument(
        '-sf', '--style-file',
        dest='style_file',
        help=f"Optional style file path for -i/--import. Default is 'pipeline.lua' otherwise.",
        required=False
    )
    parser.add_argument(
        '-sch', '--schema',
        dest='schema',
        help="Optional schema argument for -i/--import. Default is 'public' otherwise.",
        required=False
    )
    parser.add_argument(
        '--force',
        dest='force',
        action="store_true",
        help="Force overwrite of data in existing tables in schema.",
        required=False
    )
    parser.add_argument(
        "-W",
        dest="password",
        action="store_true",
        help="Force password prompt instead of using pgpass file.")

    return parser


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
