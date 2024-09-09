import argparse
import logging

import psycopg2.errors

from roadgraphtool.db_operations import (
    assign_average_speed_to_all_segments_in_area, compute_speeds_for_segments,
    compute_speeds_from_neighborhood_segments, compute_strong_components,
    contract_graph_in_area, get_area_for_demand, insert_area,
    select_network_nodes_in_area)
from roadgraphtool.export import get_map_nodes_from_db
# from roadgraphtool.credentials_config import CREDENTIALS
from scripts.process_osm import import_osm_to_db


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
        action="store_true",
        help="An option indicating if specific functions should process speed data. Default is set to False.",
        default=False,
        required=False,
    )
    parser.add_argument(
        "-i",
        "--import",
        dest="importing",
        action="store_true",
        help="Import OSM data to database specified in config.ini",
    )
    parser.add_argument(
        "-S",
        "--Style",
        help='Filename of the osm2pgsql style import in the directory "resources/lua_styles".'
        + '\nDefault is set to "pipeline.lua"',
        default="pipeline.lua",
        required=False,
    )

    return parser


def main(arg_list: list[str] | None = None):
    parser = configure_arg_parser()
    args = parser.parse_args(arg_list)

    if args.importing:
        logging.info("Importing OSM data to database...")
        retcode = import_osm_to_db(filename=args.importing, style_filename=args.Style)
        if retcode != 0:
            logging.error(f"Error during OSM data import. Return code: {retcode}")
            return retcode
        logging.info("OSM data imported successfully.")

    area_id = args.area_id
    area_srid = args.area_srid
    fill_speed = args.fill_speed

    logging.info("selecting nodes")
    nodes = select_network_nodes_in_area(area_id)
    logging.info("selected network nodes in area_id = {}".format(area_id))
    print(nodes)

    logging.info("contracting graph")
    contract_graph_in_area(area_id, area_srid, fill_speed)

    logging.info("computing strong components for area_id = {}".format(area_id))
    compute_strong_components(area_id)
    logging.info("storing the results in the component_data table")

    # insert_area("test1", [])

    area = get_area_for_demand(
        4326,
        [1, 2, 3],
        [1, 2, 3],
        1000,
        5,
        "2023-01-01 00:00:00",
        "2023-12-31 23:59:59",
        (50.0, 10.0),
        5000,
    )
    print(area)

    logging.info("Execution of assign_average_speeds_to_all_segments_in_area")
    try:
        assign_average_speed_to_all_segments_in_area(area_id, area_srid)
    except psycopg2.errors.InvalidParameterValue as e:
        logging.info("Expected Error: ", e)

    nodes = get_map_nodes_from_db(area_id)
    print(nodes)

    logging.info("Execution of compute_speeds_for_segments")
    compute_speeds_for_segments(area_id, 1, 12, 1)

    logging.info("Execution of compute_speeds_from_neighborhood_segments")
    compute_speeds_from_neighborhood_segments(area_id, area_srid)

    return 0


if __name__ == "__main__":
    exit(main())
