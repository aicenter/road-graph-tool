import json
import logging
import psycopg2
import sqlalchemy
import psycopg2.errors
import geopandas as gpd
from sshtunnel import SSHTunnelForwarder
from credentials_config import CREDENTIALS


def get_sql_alchemy_engine_str(config: CREDENTIALS, server_port):
    sql_alchemy_engine_str = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'.format(
        user=config.username,
        password=config.db_password,
        host=config.db_host,
        port=server_port,
        dbname=config.db_name)

    return sql_alchemy_engine_str


def get_map_nodes_from_db(config: dict, server_port, area_id : int) -> gpd.GeoDataFrame:
    logging.info("Fetching nodes from db")
    sql = f"""
    DROP TABLE IF EXISTS demand_nodes;

    CREATE TEMP TABLE demand_nodes(
        id int,
        db_id bigint,
        x float,
        y float,
        geom geometry
    );

    INSERT INTO demand_nodes
    SELECT * FROM select_network_nodes_in_area({area_id}::smallint);

    SELECT
        id,
        db_id,
        x,
        y,
        geom
    FROM demand_nodes
    """
    sql_alchemy_engine_str = get_sql_alchemy_engine_str(config, server_port)
    logging.info("Starting sql_alchemy connection")
    sqlalchemy_engine = sqlalchemy.create_engine(sql_alchemy_engine_str)

    return gpd.read_postgis(sql, sqlalchemy_engine)


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


if __name__ == '__main__':

    area_id = 13
    area_srid = 0
    config = CREDENTIALS

    SERVER_PORT = 22

    try:
        with SSHTunnelForwarder(
                ssh_pkey=config.private_key_path,
                ssh_username=config.server_username,
                ssh_address_or_host=(config.server, SERVER_PORT),
                remote_bind_address=(config.host, config.db_server_port),
                ssh_private_key_password=config.private_key_phrase) as server:
            server.start()
            logging.info('server connected')

            connection = psycopg2.connect(dbname=config.db_name,
                                          user=config.username,
                                          password=config.db_password,
                                          host=config.db_host, port=server.local_bind_port)
            cur = connection.cursor()
            logging.info('database connected')

            logging.info('selecting nodes')
            nodes = select_network_nodes_in_area(cur, target_area_id=area_id)
            logging.info('selected network nodes in area_id = {}'.format(area_id))
            print(nodes)

            logging.info('contracting graph')
            contract_graph_in_area(cur, target_area_id=area_id, target_area_srid=area_srid)

            logging.info('computing strong components for area_id = {}'.format(area_id))
            compute_strong_components(cur, target_area_id=area_id)
            logging.info('storing the results in the component_data table')

            insert_area(cur, 'test1', [])

            area = get_area_for_demand(cur, 4326, [1, 2, 3], [1, 2, 3], 1000,
                                       5, '2023-01-01 00:00:00', '2023-12-31 23:59:59',
                                       (50.0, 10.0), 5000)
            print(area)

            logging.info('Execution of assign_average_speeds_to_all_segments_in_area')
            try:
                assign_average_speed_to_all_segments_in_area(cur, area_id, area_srid)
            except psycopg2.errors.InvalidParameterValue as e:
                logging.info("Expected Error: ", e)

            nodes = get_map_nodes_from_db(config, server.local_bind_port, area_id)
            print(nodes)

            connection.commit()
            logging.info('commit')

            connection.rollback()
            logging.info('rollback')

            if connection:
                cur.close()
                connection.close()

    except Exception as e:
        logging.error('Connection Failed:', e)
