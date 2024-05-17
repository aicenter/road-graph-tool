import logging
import psycopg2.errors
from sshtunnel import SSHTunnelForwarder
from credentials_config import CREDENTIALS


from map import get_map_nodes_from_db, get_map_edges_from_db
from database_operations import (select_network_nodes_in_area, compute_strong_components, contract_graph_in_area,
                                 insert_area, get_area_for_demand, assign_average_speed_to_all_segments_in_area)


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
