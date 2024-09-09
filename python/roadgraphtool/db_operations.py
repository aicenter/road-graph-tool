from roadgraphtool.db import db

from .insert_area import insert_area


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


def contract_graph_in_area(
    target_area_id: int, target_area_srid: int, fill_speed: bool = True
):
    sql_query = f'call public.contract_graph_in_area({target_area_id}::smallint, {target_area_srid}::int{", FALSE" if not fill_speed else ""})'
    db.execute_sql(sql_query)


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
    sql_query = f"call public.compute_strong_components({target_area_id}::smallint)"
    db.execute_sql(sql_query)


def compute_speeds_for_segments(
    target_area_id: int,
    speed_records_dataset: int,
    hour: int,
    day_of_week: int,
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
