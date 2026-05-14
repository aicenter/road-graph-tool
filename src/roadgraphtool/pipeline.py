import logging
from typing import Optional, Dict, Any

from roadgraphtool.db import db
import roadgraphtool.road_import
import roadgraphtool.insert_area
import roadgraphtool.export
import roadgraphtool.distance_matrix_generator


def insert_area_if_area_insertion_activated(config) -> Optional[int]:
    section = getattr(config, "area_insert", None)
    if section is None or not getattr(section, "activated", False):
        return None
    description = getattr(section, "description", None)
    if description is None:
        description = "Pipeline area insert"
    logging.info("Inserting area (area_insert step)")
    return roadgraphtool.insert_area.genereate_area(config, description)


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


def main(config: Dict[str, Any]):
    area_id = getattr(config, "area_id", None)
    area_id = insert_area_if_area_insertion_activated(config) or area_id

    road_import = getattr(config, "road_import", None)
    if road_import is not None and getattr(road_import, "activated", False):
        area_id = roadgraphtool.road_import.import_road_network(config, area_id)

    if not area_id:
        area_id = config.area_id

    if hasattr(config, "contraction") and config.contraction.activated:
        contract_graph_in_area(area_id, config.srid, False)

    if hasattr(config, "strong_components") and config.strong_components.activated:
        compute_strong_components(area_id)

    nodes = None
    edges = None
    if hasattr(config, "export") and config.export.activated:
        nodes, edges = roadgraphtool.export.export(config)

    if hasattr(config, "dm_generator") and config.dm_generator.activated:
        roadgraphtool.distance_matrix_generator.generate_dm(config, nodes, edges)
    
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
