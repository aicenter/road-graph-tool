import argparse
import json
import logging
import sys

from pathlib import Path
from roadgraphtool.config import parse_config_file, set_logging
import roadgraphtool.db
from roadgraphtool.db import db
from roadgraphtool.process_osm import import_osm_to_db
import roadgraphtool.export


def get_area_for_demand(
        srid_plain: int,
        dataset_ids: list,
        zone_types: list,
        buffer_meters: int,
        min_requests_in_zone: int,
        datetime_min: str,
        datetime_max: str,
        center_point: tuple,
        max_distance_from_center_point_meters: int,
) -> list:
    sql_query = """
            select * from get_area_for_demand(
                    srid_plain := :srid_plain,
                    dataset_ids := (:dataset_ids)::smallint[],
                    zone_types := (:zone_types)::smallint[],
                    buffer_meters := (:buffer_meters)::smallint,
                    min_requests_in_zone := (:min_requests_in_zone)::smallint,
                    datetime_min := :datetime_min,
                    datetime_max := :datetime_max,
                    center_point := st_makepoint(:center_x, :center_y),
                    max_distance_from_center_point_meters := (:max_distance_from_center_point_meters)::smallint
            );"""
    params = {
        "srid_plain": srid_plain,
        "dataset_ids": dataset_ids,
        "zone_types": zone_types,
        "buffer_meters": buffer_meters,
        "min_requests_in_zone": min_requests_in_zone,
        "datetime_min": datetime_min,
        "datetime_max": datetime_max,
        "center_x": center_point[0],
        "center_y": center_point[1],
        "max_distance_from_center_point_meters": max_distance_from_center_point_meters,
    }
    return db.execute_sql_and_fetch_all_rows(sql_query, params)


def insert_area(name: str, coordinates: list):
    geom_json = {"type": "MultiPolygon", "coordinates": coordinates}
    params = {"name": name, "json_data": json.dumps(geom_json)}
    sql_query = """insert into areas (name, geom) values (:name, st_geomfromgeojson(:json_data))"""
    db.execute_sql(sql_query, params)


def contract_graph_in_area(
    target_area_id: int, target_area_srid: int, fill_speed: bool = True
):
    logging.info("Contracting graph")
    sql_query = f'call public.contract_graph_in_area({target_area_id}::smallint, {target_area_srid}::int{", FALSE" if not fill_speed else ""})'
    result = db.execute_sql(sql_query)
    logging.info("Graph Contracted")


def select_network_nodes_in_area(target_area_id: int) -> list:
    sql_query = (
        f"select * from select_network_nodes_in_area({target_area_id}::smallint)"
    )
    return db.execute_sql_and_fetch_all_rows(sql_query)


def assign_average_speed_to_all_segments_in_area(
        target_area_id: int, target_area_srid: int
):
    sql_query = (
        f"call public.assign_average_speed_to_all_segments_in_area({target_area_id}::smallint, "
        f"{target_area_srid}::int)"
    )
    db.execute_sql(sql_query)


def compute_strong_components(target_area_id: int):
    logging.info("computing strong components for area_id = {}".format(target_area_id))
    sql_query = f"call public.compute_strong_components({target_area_id}::smallint)"
    db.execute_sql(sql_query)
    logging.info("storing the results in the component_data table")


def compute_speeds_for_segments(
        target_area_id: int, speed_records_dataset: int, hour: int, day_of_week: int
):
    sql_query = (
        f"call public.compute_speeds_for_segments({target_area_id}::smallint, "
        f"{speed_records_dataset}::smallint, {hour}::smallint, {day_of_week}::smallint)"
    )
    db.execute_sql(sql_query)


def compute_speeds_from_neighborhood_segments(
        target_area_id: int, target_area_srid: int
):
    sql_query = (
        f"call public.compute_speeds_from_neighborhood_segments({target_area_id}::smallint, "
        f"{target_area_srid}::int)"
    )
    db.execute_sql(sql_query)


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
    roadgraphtool.db.db.start_or_restart_ssh_connection_if_needed()


    area_id = None

    if config.importer.activated:
        area_id = import_osm_to_db(config)

    if not area_id:
        area_id = config.area_id

    if config.contraction.activated:
        contract_graph_in_area(area_id, config.srid, False)

    if config.strong_components.activated:
        compute_strong_components(area_id)

    if config.export.activated:
        roadgraphtool.export.export(config, area_id)
    
    # logging.info("Execution of assign_average_speeds_to_all_segments_in_area")
    # try:
    #     assign_average_speed_to_all_segments_in_area(area_id, area_srid)
    # except psycopg2.errors.InvalidParameterValue as e:
    #     logging.info("Expected Error: ", e)
    #
    # nodes = get_map_nodes_from_db(area_id)
    # print(nodes)
    #
    # logging.info("Execution of compute_speeds_for_segments")
    # compute_speeds_for_segments(area_id, 1, 12, 1)
    #
    # logging.info("Execution of compute_speeds_from_neighborhood_segments")
    # compute_speeds_from_neighborhood_segments(area_id, area_srid)


if __name__ == '__main__':
    main()
