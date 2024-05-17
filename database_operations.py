import json


def get_area_for_demand(cursor, srid_plain: int, dataset_ids: list, zone_types: list,
                        buffer_meters: int, min_requests_in_zone: int, datetime_min: str,
                        datetime_max: str, center_point: tuple, max_distance_from_center_point_meters: int) -> list:
    cursor.execute("""
        select *
        from get_area_for_demand(
                srid_plain := %s,
                dataset_ids := %s::smallint[],
                zone_types := %s::smallint[],
                buffer_meters := %s::smallint,
                min_requests_in_zone := %s::smallint,
                datetime_min := %s,
                datetime_max := %s,
                center_point := st_makepoint(%s, %s),
                max_distance_from_center_point_meters := %s::smallint
        );"""
                   , (srid_plain, dataset_ids, zone_types, buffer_meters, min_requests_in_zone,
                      datetime_min, datetime_max, center_point[0], center_point[1],
                      max_distance_from_center_point_meters))
    return cursor.fetchall()


def insert_area(cursor, name: str, coordinates: list):
    geom_json = {"type": "MultiPolygon", "coordinates": coordinates}
    cursor.execute("insert into areas (name, geom) values (%s, st_geomfromgeojson(%s));",
                   (name, json.dumps(geom_json)))


def contract_graph_in_area(cursor, target_area_id: int, target_area_srid: int):
    cursor.execute('call public.contract_graph_in_area(%s::smallint, %s::int);',
                   (target_area_id, target_area_srid))


def select_network_nodes_in_area(cursor, target_area_id: int) -> list:
    cursor.execute('select * from select_network_nodes_in_area(%s::smallint);',
                   (target_area_id,))
    return cursor.fetchall()


def assign_average_speed_to_all_segments_in_area(cursor, target_area_id: int, target_area_srid: int):
    cursor.execute('call public.assign_average_speed_to_all_segments_in_area(%s::smallint, %s::int)',
                   (target_area_id, target_area_srid))


def compute_strong_components(cursor, target_area_id: int):
    cursor.execute('call public.compute_strong_components(%s::smallint)', (target_area_id,))

