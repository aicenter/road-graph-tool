import requests
import psycopg2
import psycopg2.extras
import pathlib
import sys
import time

URL = 'http://localhost:8080/elevation/api'
CHUNK_SIZE = 500


def load_coords(config):
    """Load node ids and coords from db to dict"""
    coords = list()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS temp_elevations (
        node_id BIGINT NOT NULL,
        elevation REAL
    );
    """
    # add_column_query = """ALTER TABLE nodesS ADD COLUMN IF NOT EXISTS elevation REAL;"""
    add_column_query = """ALTER TABLE nodes ADD COLUMN IF NOT EXISTS elevation REAL;"""
    # select_query = """ SELECT node_id, ST_Y(geom), ST_X(geom) FROM nodesS; """
    select_query = """ SELECT node_id, ST_Y(geom), ST_X(geom) FROM nodes; """
    # print("Loading coords...")
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_query)
                cur.execute(add_column_query)
                cur.execute(select_query)
                chunk = []
                for row in cur.fetchall():
                    # node_id, latitude, longitude
                    chunk.append([row[0], row[1], row[2]])
                    if len(chunk) == CHUNK_SIZE:
                        coords.append(chunk)
                        chunk = []
                if chunk:
                    coords.append(chunk)
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)
    return coords


def prepare_coords(coords_chunk_list):
    """Prepare json with coords for api request"""
    # print("Preparing coords...")
    chunk_json_list = list()
    for chunk in coords_chunk_list:
        json_coord_dict = {'locations': []}
        for data in chunk:
            coords = {"lat": data[1], "lon": data[2]}
            json_coord_dict['locations'].append(coords)
        chunk_json_list.append(json_coord_dict)
    return chunk_json_list


def get_elevation(chunk_json_data):
    """Send request to api and get elevation data"""
    print("Getting elevations...")
    updated_json_data = []
    for chunk in chunk_json_data:
        chunk_response = requests.post(URL, json=chunk)
        updated_json_data.append(chunk_response.json())
        if chunk_response.status_code != 200:
            print("Error:", chunk_response.status_code)
    return updated_json_data


def update_elevations(coords_list, updated_chunk_list):
    """Update elevations: add elevation to dict containing info about nodes"""
    print("Updating coords with elevations...")
    for i in range(len(coords_list)):
        chunk_locations = updated_chunk_list[i].get('locations', [])
        for j, location in enumerate(chunk_locations):
            ele = location.get('ele')
            coords_list[i][j].append(ele)
    return coords_list


def store_elevations(config, elevations):
    """Store elevation from elevations dict to db"""
    print("Storing elevations...")
    insert_query = """ INSERT INTO temp_elevations (node_id, elevation) VALUES %s; """
    # update_query = """ UPDATE nodes_germany SET elevation = elevations.elevation FROM (VALUES %s) AS elevations (node_id, elevation) WHERE nodes_germany.node_id = elevations.node_id; """
    # node_id, elevation
    data_tuples = [(data[0], data[3]) for chunk in elevations for data in chunk]
    try:
        with psycopg2.connect(**config) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, insert_query, data_tuples)
                # for chunk in elevations:
                    # node_id, elevation
                    # data_tuples = [(data[0], data[3]) for data in chunk]
                    # psycopg2.extras.execute_values(cur, insert_query, data_tuples)
                    # psycopg2.extras.execute_values(cur, insert, data_tuples, template='(%s, %s)')
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def update_nodes_and_drop_elevations(config):
    """Update nodes table with elevations and drop elevations table"""
    update_query = """
    UPDATE nodes_germany
    SET elevation = temp_elevations.elevation
    FROM temp_elevations
    WHERE nodes_germany.node_id = temp_elevations.node_id;
    """
    drop_table_query = """DROP TABLE temp_elevations;"""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(update_query)
                cur.execute(drop_table_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def run(config):
    coords = load_coords(config)
    json_coords = prepare_coords(coords)
    json_elevations = get_elevation(json_coords)
    elevations = update_elevations(coords, json_elevations)
    store_elevations(config, elevations)
    # update_nodes_and_drop_elevations(config)


if __name__ == '__main__':
    # Use credentials_config from parent directory
    parent_dir = pathlib.Path(__file__).parent.parent
    sys.path.append(str(parent_dir))
    from roadgraphtool.credentials_config import CREDENTIALS
    config = {
        "host": CREDENTIALS.host,
        "dbname": CREDENTIALS.db_name,
        "user": CREDENTIALS.username,
        "password": CREDENTIALS.db_password,
        "port": CREDENTIALS.db_server_port
    }

    start = time.time()
    # run(config)

    coords = load_coords(config)
    e = time.time()
    print(f"Loading coords... {e - start} seconds.")

    s = time.time()
    json_coords = prepare_coords(coords)
    e = time.time()
    print(f"Preparing coords... {e - s} seconds.")

    # s = time.time()
    # json_elevations = get_elevation(json_coords)
    # e = time.time()
    # print(f"Getting coords... {e - s} seconds.")

    # s = time.time()
    # elevations = update_elevations(coords, json_elevations)
    # e = time.time()
    # print(f"Updating coords with elevations... {e - s} seconds.")

    # s = time.time()
    # store_elevations(config, elevations)
    # e = time.time()
    # print(f"Storing elevations to table... {e - s} seconds.")

    # # s = time.time()
    # # update_nodes_and_drop_elevations(config)
    # # end = time.time()
    # # print(f"Update correct table... {e - s} seconds.")
    # print(f"The program took {e - start} seconds to execute.")
