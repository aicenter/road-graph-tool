import logging
import requests
import psycopg2
import psycopg2.extras
import argparse
import time

from roadgraphtool.credentials_config import CREDENTIALS, CredentialsConfig
from roadgraphtool.schema import get_connection
from scripts.filter_osm import setup_logger

URL = 'http://localhost:8080/elevation/api'
CHUNK_SIZE = 5000

logger = setup_logger('elevation')

def load_coords(config: CredentialsConfig, table_name: str, schema: str) -> list:
    """Returns list of node IDs and coordinations."""
    coords = list()
    query = f" SELECT node_id, ST_Y(geom), ST_X(geom) FROM {schema}.{table_name};"

    try:
        with get_connection(config) as conn:
            with conn.cursor('node_cursor') as cur:
                cur.execute(query)
                while True:
                    chunk = cur.fetchmany(CHUNK_SIZE)
                    if not chunk:
                        break
                    coords.append(chunk)
        return coords
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)

def process_chunks(config: CredentialsConfig, schema: str, chunks_list: list):
    for chunk in chunks_list:
        json_chunk = prepare_coords(chunk)
        updated_json_chunk = get_elevation(json_chunk)
        store_elevations(config, schema, json_chunk, updated_json_chunk)


def prepare_coords(chunk: list) -> dict:
    """Returns JSON with coords for API request."""
    locations_dict = {'locations': []}
    for _, lat, lon in chunk:
        locations_dict['locations'].append({"lat": lat, "lon": lon})
    return locations_dict

def get_elevation(json_chunk: dict) -> dict:
    """Sends request to API and receives updated coordinations with elevation."""
    # response = requests.post(URL, json=json_chunk)
    # if response.status_code != 200:
    #     print("Error:", response.status_code)
    # return response.json()
    for i in range(len(json_chunk['locations'])):
        json_chunk['locations'][i]['ele'] = 200
    return json_chunk

def setup_database(config: CredentialsConfig, table_name: str, schema: str):
    """Create table and column for elevations"""
    table_query = f"""
    CREATE TABLE IF NOT EXISTS {schema}.elevations (
        node_id BIGINT NOT NULL,
        elevation REAL
    );
    """
    column_query = f"""ALTER TABLE {schema}.{table_name} ADD COLUMN IF NOT EXISTS elevation REAL;"""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(table_query)
                cur.execute(column_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

def store_elevations(config: CredentialsConfig, schema: str, coord_chunk: list, elevation_chunk: list):
    """Stores elevation data from given chunks into the database table."""
    insert_query = f""" INSERT INTO {schema}.elevations (node_id, elevation) VALUES %s; """
    # data_tuples = [(data['id'], data['ele']) for _, data in elevation_chunk.items()]
    data_tuples = [(coord[0], location['ele']) 
                   for coord, location in zip(coord_chunk, elevation_chunk['locations'])]
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, insert_query, data_tuples)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

def update_and_drop_table(config: CredentialsConfig, table_name: str, schema: str):
    """Updates table with elevations and deletes elevations table."""
    update_query = f"""
    UPDATE {schema}.{table_name}
    SET elevation = {schema}.elevations.elevation
    FROM {schema}.elevations
    WHERE {schema}.{table_name}.node_id = {schema}.elevations.node_id;
    """
    drop_query = f"""DROP TABLE {schema}.elevations;"""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(update_query)
                cur.execute(drop_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process OSM files and interact with PostgreSQL database.", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('table_name', help="The name of the table where the nodes data are stored.")
    parser.add_argument("-sch", "--schema", dest="schema", default="public", help="The database schema of the table where nodes are stored.")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Enable verbose output (DEBUG level logging)")

    args = parser.parse_args(arg_list)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return args


def main(arg_list: list[str] | None = None):
    args = parse_args(arg_list)

    config = {
            "host": CREDENTIALS.host,
            "dbname": CREDENTIALS.db_name,
            "user": CREDENTIALS.username,
            "password": CREDENTIALS.db_password,
            "port": CREDENTIALS.db_server_port
        }
    
    table_name = args.table_name
    schema = args.schema

    start = time.time()

    setup_database(config, table_name, schema)
    coords = load_coords(config, table_name, schema)
    process_chunks(config, schema, coords)
    update_and_drop_table(config, table_name, schema)
    
    end = time.time()

    print(f"The program took {end - start} seconds to execute.")


if __name__ == '__main__':
    main()
