import psycopg2
from credentials_config import CREDENTIALS
from sshtunnel import SSHTunnelForwarder


def create_road_segments(cursor, target_area_id: int, target_area_srid: int):
    print('Creating road segments table')
    cursor.execute('CREATE TEMPORARY TABLE road_segments AS '
                   '(SELECT * FROM select_node_segments_in_area(%s::smallint, %s::int))',
                   (target_area_id, target_area_srid))
    cursor.execute('CREATE INDEX road_segments_index_from_to ON road_segments (from_id, to_id)')
    cursor.execute('SELECT count(*) FROM road_segments')
    segments_cnt = cursor.fetchone()[0]
    print('Road segments table created: ' + str(segments_cnt) + ' road segments')


def contract_graph(cursor):
    print('Contracting graph')
    cursor.execute(
        'CREATE TEMPORARY TABLE contractions AS ('
        'SELECT id, source, target, unnest(contracted_vertices) AS contracted_vertex '
        'FROM pgr_contraction(\'SELECT row_number() OVER () AS id, "from_node" AS source, '
        '"to_node" AS target, 0 AS cost FROM road_segments\', ARRAY[2]))')
    cursor.execute('CREATE INDEX contractions_index_contracted_vertex ON contractions (contracted_vertex)')
    cursor.execute('CREATE INDEX contractions_index_from_to ON contractions (source, target)')
    cursor.execute('SELECT count(*) FROM contractions')
    contractions_cnt = cursor.fetchone()[0]
    print(str(contractions_cnt) + ' nodes contracted')


def update_nodes(cursor):
    print('Updating nodes')
    cursor.execute('UPDATE nodes SET contracted = TRUE '
                   'WHERE id IN (SELECT contracted_vertex FROM contractions)')


def create_edges_non_contracted(cursor, target_area_id: int):
    print('Creating edges for non-contracted road segments')
    cursor.execute(
        'INSERT INTO edges ("from", "to", geom, area, speed) '
        'SELECT road_segments.from_node, road_segments.to_node, st_multi(st_makeline(from_nodes.geom, to_nodes.geom)) '
        'as geom, %s::smallint AS area, speed '
        'FROM road_segments '
        'JOIN nodes from_nodes ON from_nodes.id = from_node AND from_nodes.contracted = FALSE '
        'JOIN nodes to_nodes ON to_nodes.id = to_node AND to_nodes.contracted = FALSE '
        'JOIN ways ON ways.id = road_segments.way_id', (target_area_id,))
    cursor.execute('SELECT count(*) FROM edges WHERE area = %s::smallint', (target_area_id,))
    non_contracted_edges_cnt = cursor.fetchone()[0]
    print(str(non_contracted_edges_cnt) + ' Edges for non-contracted road segments created')
    return non_contracted_edges_cnt


def create_contraction_segments(cursor):
    print('Generating contraction segments')
    cursor.execute(
        'CREATE TEMPORARY TABLE contraction_segments AS ('
        'SELECT from_contraction.id, from_contraction.contracted_vertex AS from_node, '
        'to_contraction.contracted_vertex AS to_node, geom, speed '
        'FROM contractions from_contraction '
        'JOIN contractions to_contraction ON from_contraction.id = to_contraction.id '
        'JOIN road_segments ON road_segments.from_node = from_contraction.contracted_vertex AND '
        'road_segments.to_node = to_contraction.contracted_vertex '
        'UNION SELECT id, source AS from_node, contracted_vertex AS to_node, geom, speed '
        'FROM contractions '
        'JOIN road_segments ON road_segments.from_node = '
        'source AND road_segments.to_node = contracted_vertex '
        'UNION SELECT id, contracted_vertex AS from_node, '
        'target AS to_node, geom, speed FROM contractions '
        'JOIN road_segments ON road_segments.from_node = contracted_vertex AND road_segments.to_node = target)')
    cursor.execute('SELECT count(*) FROM contraction_segments')
    generated_segments_cnt = cursor.fetchone()[0]
    print(str(generated_segments_cnt) + ' contraction segments generated')


def create_edges_contracted(cursor, target_area_id: int, non_contracted_edges_cnt: int):
    print('Creating edges for contracted road segments')
    cursor.execute(
        'INSERT INTO edges ("from", "to", area, geom, speed) '
        'SELECT max(source) AS "from", max(target) AS "to", %s::smallint AS area, '
        'st_transform(st_multi(st_union(geom)), 4326) AS geom, '
        'sum(speed * st_length(geom)) / sum(st_length(geom)) AS speed '
        'FROM contractions JOIN contraction_segments ON contraction_segments.id = contractions.id '
        'GROUP BY contractions.id', (target_area_id,))
    cursor.execute('SELECT count(*) FROM edges WHERE area = %s::smallint', (target_area_id,))
    edges_cnt = cursor.fetchone()[0] - non_contracted_edges_cnt
    print(str(edges_cnt) + ' Edges for contracted road segments created')


def contract_graph_in_area(cursor, target_area_id: int, target_area_srid: int):
    create_road_segments(cursor, target_area_id, target_area_srid)
    contract_graph(cur)
    update_nodes(cur)
    non_contracted_edges_cnt = create_edges_non_contracted(cur, target_area_id)
    create_contraction_segments(cur)
    create_edges_contracted(cur, target_area_id, non_contracted_edges_cnt)


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

            print('\n---Contracting graph---')
            contract_graph_in_area(cur, target_area_id=area_id, target_area_srid=area_srid)
            connection.commit()
            print('---Commit---')

            if connection:
                cur.close()
                connection.close()

    except Exception as e:
        print('Connection Failed:', e)
