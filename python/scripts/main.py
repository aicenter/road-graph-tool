import argparse
import json
import logging
import sys
import psycopg2.errors

from roadgraphtool.credentials_config import CREDENTIALS
from roadgraphtool.export import get_map_nodes_from_db
from roadgraphtool.db import db
from scripts.process_osm import import_osm_to_db


def get_area_for_demand(srid_plain: int, dataset_ids: list, zone_types: list,
                        buffer_meters: int, min_requests_in_zone: int, datetime_min: str,
                        datetime_max: str, center_point: tuple, max_distance_from_center_point_meters: int) -> list:
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
        'srid_plain': srid_plain,
        'dataset_ids': dataset_ids,
        'zone_types': zone_types,
        'buffer_meters': buffer_meters,
        'min_requests_in_zone': min_requests_in_zone,
        'datetime_min': datetime_min,
        'datetime_max': datetime_max,
        'center_x': center_point[0],
        'center_y': center_point[1],
        'max_distance_from_center_point_meters': max_distance_from_center_point_meters
    }
    return db.execute_sql_and_fetch_all_rows(sql_query, params)


def insert_area(name: str, coordinates: list):
    geom_json = {"type": "MultiPolygon", "coordinates": coordinates}
    params = {"name": name, "json_data": json.dumps(geom_json)}
    sql_query = """insert into areas (name, geom) values (:name, st_geomfromgeojson(:json_data))"""
    db.execute_sql(sql_query, params)


def contract_graph_in_area(target_area_id: int, target_area_srid: int):
    sql_query = f"call public.contract_graph_in_area({target_area_id}::smallint, {target_area_srid}::int)"
    db.execute_sql(sql_query)


def select_network_nodes_in_area(target_area_id: int) -> list:
    sql_query = f"select * from select_network_nodes_in_area({target_area_id}::smallint)"
    return db.execute_sql_and_fetch_all_rows(sql_query)


def assign_average_speed_to_all_segments_in_area(target_area_id: int, target_area_srid: int):
    sql_query = (f"call public.assign_average_speed_to_all_segments_in_area({target_area_id}::smallint, "
                 f"{target_area_srid}::int)")
    db.execute_sql(sql_query)


def compute_strong_components(target_area_id: int):
    sql_query = f"call public.compute_strong_components({target_area_id}::smallint)"
    db.execute_sql(sql_query)


def compute_speeds_for_segments(target_area_id: int, speed_records_dataset: int, hour: int, day_of_week: int):
    sql_query = (f"call public.compute_speeds_for_segments({target_area_id}::smallint, "
                 f"{speed_records_dataset}::smallint, {hour}::smallint, {day_of_week}::smallint)")
    db.execute_sql(sql_query)


def compute_speeds_from_neighborhood_segments(target_area_id: int, target_area_srid: int):
    sql_query = (f"call public.compute_speeds_from_neighborhood_segments({target_area_id}::smallint, "
                 f"{target_area_srid}::int)")
    db.execute_sql(sql_query)


def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter OSM files with various operations.")
    # parser = argparse.ArgumentParser(description="Filter OSM files with various operations.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-i', '--import', dest='importing', action="store_true", help='Import OSM data to database specified in config.ini')

    args = parser.parse_args(arg_list)

    return args


def main(arg_list: list[str] | None = None):
    args = parse_args(arg_list)

    area_id = 13
    area_srid = 0
    config = CREDENTIALS

    SERVER_PORT = 22

    if args.importing:
        import_osm_to_db()
    
    logging.info('selecting nodes')
    nodes = select_network_nodes_in_area(area_id)
    logging.info('selected network nodes in area_id = {}'.format(area_id))
    print(nodes)

    logging.info('contracting graph')
    contract_graph_in_area(area_id, area_srid)

    logging.info('computing strong components for area_id = {}'.format(area_id))
    compute_strong_components(area_id)
    logging.info('storing the results in the component_data table')

    insert_area('test1', [])

    area = get_area_for_demand(4326, [1, 2, 3], [1, 2, 3], 1000,
                               5, '2023-01-01 00:00:00', '2023-12-31 23:59:59',
                               (50.0, 10.0), 5000)
    print(area)

    logging.info('Execution of assign_average_speeds_to_all_segments_in_area')
    try:
        assign_average_speed_to_all_segments_in_area(area_id, area_srid)
    except psycopg2.errors.InvalidParameterValue as e:
        logging.info("Expected Error: ", e)

    nodes = get_map_nodes_from_db(area_id)
    print(nodes)

    logging.info('Execution of compute_speeds_for_segments')
    compute_speeds_for_segments(area_id, 1, 12, 1)

    logging.info('Execution of compute_speeds_from_neighborhood_segments')
    compute_speeds_from_neighborhood_segments(area_id, area_srid)

if __name__ == '__main__':
    main()