import logging
import os
import requests
import psycopg2
import psycopg2.extras
import argparse
import time
import numpy as np
import csv

from roadgraphtool.credentials_config import CREDENTIALS as config
from roadgraphtool.schema import get_connection
from roadgraphtool.log import LOGGER

URL = 'http://localhost:8080/elevation/api'
CHUNK_SIZE = 5000

logger = LOGGER.get_logger('elevation')

def load_coords(table_name: str, schema: str) -> np.ndarray:
    """Return a list of node IDs and coordinations."""
    coords = []
    query = f" SELECT node_id, ST_Y(geom), ST_X(geom) FROM {schema}.{table_name};"

    try:
        with get_connection() as conn:
            logger.info("Connected to the database.")
            logger.info("Loading coordinates...")
            with conn.cursor('node_cursor') as cur:
                cur.execute(query)
                while True:
                    chunk = cur.fetchmany(CHUNK_SIZE)
                    if not chunk:
                        break
                    coords.extend(chunk)
        logger.info("Coordinates loaded.")
        # logger.info("Coordinate shape: %s", np.array(coords, dtype=object).shape)
        return np.array(coords, dtype=object)
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def process_chunks(schema: str, file_name: str, chunks_array: np.ndarray):
    logger.info("Processing chunks...")
    for chunk in np.array_split(chunks_array, len(chunks_array) // CHUNK_SIZE + 1):
        json_chunk = prepare_coords(chunk)
        updated_json_chunk = get_elevation(json_chunk)
        save_chunk_to_csv(file_name, chunk, updated_json_chunk)
        # store_elevations(schema, chunk, updated_json_chunk)
    logger.info("Chunks processed and stored to CSV.")
    # logger.info("Chunks processed and stored to DB.")

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

def save_chunk_to_csv(file_path: str, coord_chunk: list, elevation_chunk: list):
    if not elevation_chunk or 'locations' not in elevation_chunk:
        return
    keys = ['node_id', 'ele']
    data_tuples = [(coord[0], location['ele']) 
                   for coord, location in zip(coord_chunk, elevation_chunk['locations'])]
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)

        if csvfile.tell() == 0:
            writer.writerow(keys)

        writer.writerows(data_tuples)

def setup_database(table_name_orig: str, table_name_dest: str, schema: str):
    """Create table and column for elevations."""
    table_query = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{table_name_dest} (
        node_id BIGINT NOT NULL,
        elevation REAL
    );
    """
    column_query = f"""ALTER TABLE {schema}.{table_name_orig} ADD COLUMN IF NOT EXISTS elevation REAL;"""
    try:
        logger.info("Setting up database...")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(table_query)
                cur.execute(column_query)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")
    logger.info("Database setup.")

def store_elevations(schema: str, coord_chunk: list, elevation_chunk: list):
    """Store elevation data from given chunks into the database table."""
    insert_query = f""" INSERT INTO {schema}.elevations (node_id, elevation) VALUES %s; """
    data_tuples = [(coord[0], location['ele']) 
                   for coord, location in zip(coord_chunk, elevation_chunk['locations'])]
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, insert_query, data_tuples)
        conn.commit()
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")
    
def copy_csv_to_postgresql(schema: str, table_name: str, file_name: str):
    copy_query = f"""
    COPY {schema}.{table_name} (node_id, elevation)
    FROM STDIN WITH CSV HEADER
    DELIMITER AS ','"""
    try:
        logger.info("Copying CSV with elevations to PostgreSQL database...")
        with get_connection() as conn:
            with conn.cursor() as cur:
                with open(file_name, 'r') as f:
                    cur.copy_expert(copy_query, f)
        conn.commit()
        logger.info("CSV with elevations successfully copied to PostgreSQL database.")
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def update_and_drop_table(table_name_orig: str, table_name_dest: str, schema: str, coords: np.ndarray):
    """Update the original table with elevations and drop the temporary table."""
    index_query_orig = f"""CREATE INDEX IF NOT EXISTS {table_name_orig}_node_id_idx ON {schema}.{table_name_orig} (node_id);"""
    index_query_dest = f"""CREATE INDEX IF NOT EXISTS {table_name_dest}_node_id_idx ON {schema}.{table_name_dest} (node_id);"""
    drop_query = f"""DROP TABLE {schema}.{table_name_dest};"""
    
    node_ids = coords[:, 0]
    node_ids = np.array_split(node_ids, len(node_ids) // CHUNK_SIZE + 1)
    try:
        logger.info("Updating and dropping tables...")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(index_query_orig)
                cur.execute(index_query_dest)
                for chunk in node_ids:
                    update_query = f"""
                    UPDATE {schema}.{table_name_orig} AS orig
                    SET elevation = dest.elevation
                    FROM {schema}.{table_name_dest} AS dest
                    WHERE orig.node_id = dest.node_id
                    AND orig.node_id IN ({','.join(map(str, chunk))});
                    """
                    cur.execute(update_query)
                cur.execute(drop_query)
        conn.commit()
        logger.info("Tables updated and dropped.")
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add elevations to nodes in PostgreSQL database.", formatter_class=argparse.RawTextHelpFormatter)

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

    table_name_orig = args.table_name
    schema = args.schema
    table_name_dest = "elevations"
    elevation_file = f"/Users/domisidlova/Desktop/smart-mobility/road-graph-tool/{table_name_dest}.csv"

    start = time.time()

    setup_database(table_name_orig, table_name_dest, schema)
    coords = load_coords(table_name_orig, schema)
    process_chunks(schema, elevation_file, coords)
    copy_csv_to_postgresql(schema, table_name_dest, elevation_file)

    # update_and_drop_table(table_name_orig, table_name_dest, schema, coords)
    
    end = time.time()

    logger.info(f"The program took {end - start} seconds to execute.")

    if os.path.exists(elevation_file):
        os.remove(elevation_file)
        logger.info(f"Removed elevation file: {elevation_file}")
    else:
        logger.warning(f"Elevation file not found: {elevation_file}")

if __name__ == '__main__':
    print("With indexing")
    main()
    # main(['nodes', '-sch', 'testing'])
