import logging
from typing import Optional, Dict, Any

from roadgraphtool.db import db
import roadgraphtool.road_import
import roadgraphtool.insert_area
import roadgraphtool.export
import roadgraphtool.distance_matrix_generator
import roadgraphtool.schema
import roadgraphtool.viewer
import roadgraphtool.viewer_deploy


def _is_activated(config, step: str) -> bool:
    """Whether the pipeline *step* is configured and activated. A section without ``activated`` (e.g., only with
    credentials from the secrets file) is not activated."""
    return getattr(getattr(config, step, None), "activated", False)


def insert_area_if_area_insertion_activated(config) -> Optional[int]:
    if not _is_activated(config, "area_insert"):
        return None
    section = config.area_insert
    description = getattr(section, "description", None)
    if description is None:
        description = "Pipeline area insert"
    logging.info("Inserting area (area_insert step)")
    return roadgraphtool.insert_area.genereate_area(config, description)


def contract_graph_in_area(
    target_area_id: int, target_area_srid: int, fill_speed: bool = True
):
    logging.info("Contracting graph")
    if fill_speed:
        db.execute_procedure(
            "contract_graph_in_area",
            (target_area_id, "smallint"),
            (target_area_srid, "int"),
        )
    else:
        db.execute_procedure(
            "contract_graph_in_area",
            (target_area_id, "smallint"),
            (target_area_srid, "int"),
            (False, "boolean"),
        )
    logging.info("Graph Contracted")


def select_network_nodes_in_area(target_area_id: int) -> list:
    sql_query = (
        f"select * from select_network_nodes_in_area({target_area_id}::smallint)"
    )
    return db.execute_sql_and_fetch_all_rows(sql_query)


def assign_average_speed_to_all_segments_in_area(
        target_area_id: int, target_area_srid: int
):
    db.execute_procedure(
        "assign_average_speed_to_all_segments_in_area",
        (target_area_id, "smallint"),
        (target_area_srid, "int"),
    )


def compute_strong_components(target_area_id: int):
    logging.info("computing strong components for area_id = {}".format(target_area_id))
    db.execute_procedure(
        "compute_strong_components",
        (target_area_id, "smallint"),
    )
    logging.info("storing the results in the component_data table")


def compute_speeds_for_segments(
        target_area_id: int, speed_records_dataset: int, hour: int, day_of_week: int
):
    db.execute_procedure(
        "compute_speeds_for_segments",
        (target_area_id, "smallint"),
        (speed_records_dataset, "smallint"),
        (hour, "smallint"),
        (day_of_week, "smallint"),
    )


def compute_speeds_from_neighborhood_segments(
        target_area_id: int, target_area_srid: int
):
    db.execute_procedure(
        "compute_speeds_from_neighborhood_segments",
        (target_area_id, "smallint"),
        (target_area_srid, "int"),
    )


def main(config: Dict[str, Any]):
    roadgraphtool.schema.ensure_schema(config)

    area_id = getattr(config, "area_id", None)
    area_id = insert_area_if_area_insertion_activated(config) or area_id

    if _is_activated(config, "road_import"):
        area_id = roadgraphtool.road_import.import_road_network(config, area_id)

    if not area_id:
        area_id = config.area_id
    # the export reads the area from the config, so pass on an area created or found by the steps above
    config.area_id = area_id

    if _is_activated(config, "contraction"):
        contract_graph_in_area(area_id, config.srid, False)

    if _is_activated(config, "strong_components"):
        compute_strong_components(area_id)

    nodes = None
    edges = None
    if _is_activated(config, "export"):
        nodes, edges = roadgraphtool.export.export(config)

    if _is_activated(config, "dm_generator"):
        roadgraphtool.distance_matrix_generator.generate_dm(config, nodes, edges)

    if _is_activated(config, "viewer"):
        roadgraphtool.viewer.build_viewer(config, nodes, edges)

    if _is_activated(config, "viewer_deploy"):
        roadgraphtool.viewer_deploy.deploy_viewer(config)
    
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
