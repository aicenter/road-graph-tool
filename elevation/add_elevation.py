import requests
import psycopg2
import psycopg2.extras
import pathlib
import sys

URL = 'http://localhost:8080/elevation/api'


def load_coords(config):
    """Load node ids and coords from db to dict"""
    elevations = dict()
    query = """ SELECT node_id, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM nodes; """
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                for row in cur.fetchall():
                    node_id, lat, lon = row
                    coords = (lat, lon)
                    elevations[coords] = {"id": node_id}
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)
    return elevations


def prepare_coords(elevation_dict):
    """Prepare json with coords for api request"""
    json_coord_dict = {
        'locations': []
    }
    for key in elevation_dict:
        coords = {"lat": key[0], "lon": key[1]}
        json_coord_dict['locations'].append(coords)
    return json_coord_dict


def get_elevation(json_data):
    """Send request to api and get elevation data"""
    response = requests.post(URL, json=json_data)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error:", response.status_code)
    return response.json()


def update_elevations(coords_dict, json_elevation_dict):
    """Update elevations: add elevation to dict containing info about nodes"""
    print("Start update elevations...")
    locations = json_elevation_dict.get('locations', [])
    for location in locations:
        lat = location.get('lat')
        lon = location.get('lon')
        ele = location.get('ele')
        coords = (lat, lon)
        coords_dict[coords]['ele'] = ele
    return coords_dict


def create_elevation_table_and_column(config):
    """Create table and column for elevations"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS elevations (
        node_id BIGINT NOT NULL,
        elevation REAL
    );
    """
    add_column_query = """ALTER TABLE nodes ADD COLUMN IF NOT EXISTS elevation REAL;"""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_query)
                cur.execute(add_column_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def store_elevations(config, elevations):
    """Store elevation from elevations dict to db"""
    create_elevation_table_and_column(config)
    insert_query = """ INSERT INTO elevations (node_id, elevation) VALUES %s; """
    data_tuples = [(data['id'], data['ele']) for _, data in elevations.items()]
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, insert_query, data_tuples)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def update_nodes_and_drop_elevations(config):
    """Update nodes table with elevations and drop elevations table"""
    update_query = """
    UPDATE nodes
    SET elevation = elevations.elevation
    FROM elevations
    WHERE nodes.node_id = elevations.node_id;
    """
    drop_table_query = """DROP TABLE elevations;"""
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
    update_nodes_and_drop_elevations(config)


if __name__ == '__main__':
    # Use credentials_config from parent directory
    parent_dir = pathlib.Path(__file__).parent.parent
    sys.path.append(str(parent_dir))
    from credentials_config import CREDENTIALS
    config = {
            "host": CREDENTIALS.host,
            "dbname": CREDENTIALS.db_name,
            "user": CREDENTIALS.username,
            "password": CREDENTIALS.db_password,
            "port": CREDENTIALS.db_server_port
        }

    import time
    start = time.time()
    run(config)
    end = time.time()
    print(f"The program took {end - start} seconds to execute.")
