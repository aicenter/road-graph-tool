import requests
import psycopg2
import psycopg2.extras
import json

URL = 'http://localhost:8080/elevation/api'


def load_config():
    """Load configuration of db"""
    with open('config.json') as f:
        config = json.load(f)
    return config['database']


def load_coords():
    """Load node ids and coords from db to dict"""
    db_params = load_config()
    elevations = dict()
    query = """ SELECT node_id, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM nodes; """
    try:
        with psycopg2.connect(**db_params) as conn:
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


def create_elevation_table_and_column():
    """Create table and column for elevations"""
    db_params = load_config()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS elevations (
        node_id BIGINT NOT NULL,
        elevation REAL
    );
    """
    add_column_query = """ALTER TABLE nodes ADD COLUMN IF NOT EXISTS elevation REAL;"""
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_query)
                cur.execute(add_column_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def store_elevations(elevations):
    """Store elevation from elevations dict to db"""
    db_params = load_config()
    create_elevation_table_and_column()
    insert_query = """ INSERT INTO elevations (node_id, elevation) VALUES %s; """
    data_tuples = [(data['id'], data['ele']) for _, data in elevations.items()]
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, insert_query, data_tuples)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def update_nodes_and_drop_elevations():
    """Update nodes table with elevations and drop elevations table"""
    db_params = load_config()
    update_query = """
    UPDATE nodes
    SET elevation = elevations.elevation
    FROM elevations
    WHERE nodes.node_id = elevations.node_id;
    """
    drop_table_query = """DROP TABLE elevations;"""
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                cur.execute(update_query)
                cur.execute(drop_table_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def run():
    coords = load_coords()
    json_coords = prepare_coords(coords)
    json_elevations = get_elevation(json_coords)
    elevations = update_elevations(coords, json_elevations)
    store_elevations(elevations)
    update_nodes_and_drop_elevations()


if __name__ == '__main__':
    run()
