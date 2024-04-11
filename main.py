import logging
import psycopg2
from sshtunnel import SSHTunnelForwarder
from credentials_config import CREDENTIALS


def contract_graph_in_area(cursor, target_area_id: int, target_area_srid: int):
    cursor.execute('call public.contract_graph_in_area(%s::smallint, %s::int);',
                   (target_area_id, target_area_srid))


def select_network_nodes_in_area(cursor, target_area_id: int) -> list:
    cursor.execute('select * from select_network_nodes_in_area(%s::smallint);',
                   (target_area_id,))
    return cursor.fetchall()


def compute_strong_components(cursor, target_area_id: int):
    cursor.execute('call public.compute_strong_components(%s::smallint)', (target_area_id,))


if __name__ == '__main__':

    area_id = 0
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

            connection.commit()
            logging.info('commit')

            if connection:
                cur.close()
                connection.close()

    except Exception as e:
        logging.error('Connection Failed:', e)
