import psycopg2
from credentials_config import CREDENTIALS
from sshtunnel import SSHTunnelForwarder


def contract_graph_in_area(cursor, target_area_id: int, target_area_srid: int):
    cursor.execute('call public.contract_graph_in_area(%s::smallint, %s::int);',
                   (target_area_id, target_area_srid))


if __name__ == '__main__':

    area_id = 0
    area_srid = 0
    config = CREDENTIALS

    SERVER_PORT = 22
    HOST = 'localhost'
    DBNAME = 'test_larionov'
    SERVER = 'its.fel.cvut.cz'

    try:
        with SSHTunnelForwarder(
                ssh_pkey=config.private_key_path,
                ssh_username=config.server_username,
                ssh_address_or_host=(SERVER, SERVER_PORT),
                remote_bind_address=(HOST, config.db_server_port),
                ssh_private_key_password=config.private_key_phrase) as server:
            server.start()
            print('server connected')

            connection = psycopg2.connect(dbname=DBNAME,
                                          user=config.username,
                                          password=config.db_password,
                                          host=HOST, port=server.local_bind_port)
            cur = connection.cursor()
            print('database connected')

            print('contracting graph')
            contract_graph_in_area(cur, target_area_id=area_id, target_area_srid=area_srid)
            connection.commit()
            print('commit')

            if connection:
                cur.close()
                connection.close()

    except Exception as e:
        print('Connection Failed:', e)
