import logging
import os
import requests
import psycopg2
import psycopg2.extras
import argparse
import time
import numpy as np
import csv

from roadgraphtool.credentials_config import CREDENTIALS
from roadgraphtool.schema import get_connection
from roadgraphtool.log import LOGGER

URL = 'http://localhost:8080/elevation/api'
CHUNK_SIZE = 5000

logger = LOGGER.get_logger('elevation')

def load_coords(table_name: str, schema: str) -> np.ndarray:
    """Load coordinates from the database.
    
    Args:
        table_name: Table where the node_ids and geoms are stored.
        schema: The database schema of where the table_name is stored.

    Returns:
        coords: A numpy array of node_id, lat, lon.
    """
    coords_list = []
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
                    coords_list.extend(chunk)
        logger.info("Coordinates loaded.")
        logger.debug("Coordinate shape: %s", np.array(coords_list, dtype=object).shape)
        coords = np.array(coords_list, dtype=object)
        return coords
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def process_chunks(file_path: str, chunks_array: np.ndarray):
    """Process chunks of coordinates and store them to a CSV file.
    
    Args:
        file_name: The path to the CSV file where the elevation data will be stored.
        chunks_array: A numpy array of node_id, lat, lon.
    """
    logger.info("Processing chunks...")
    for chunk in np.array_split(chunks_array, len(chunks_array) // CHUNK_SIZE + 1):
        json_chunk = prepare_coords(chunk)
        updated_json_chunk = get_elevation(json_chunk)
        save_chunk_to_csv(file_path, chunk, updated_json_chunk)
    logger.info("Chunks processed and stored to CSV.")

def prepare_coords(chunk: np.ndarray) -> dict:
    """Prepare coordinates for the API.
    
    Args:
        chunk: A numpy array of node_id, lat, lon.
        
    Returns:
        locations_dict: A dictionary of locations (contains list of dictionaries of lat, lon).
    """
    locations_dict = {'locations': []}
    for _, lat, lon in chunk:
        locations_dict['locations'].append({"lat": lat, "lon": lon})
    return locations_dict

def get_elevation(json_chunk: dict) -> dict:
    """Get elevation data from the API.
    
    Args:
        json_chunk: A dictionary of locations (contains list of dictionaries of lat, lon).
        
    Returns:
        json_chunk: An updated dictionary of locations (contains list of dictionaries of lat, lon, ele).
    """
    # response = requests.post(URL, json=json_chunk)
    # if response.status_code != 200:
    #     print("Error:", response.status_code)
    # return response.json()
    # only for testing:
    for i in range(len(json_chunk['locations'])):
        json_chunk['locations'][i]['ele'] = 200
    return json_chunk

def save_chunk_to_csv(file_path: str, coord_chunk: np.ndarray, elevation_chunk: dict):
    """Append *node_id* from coord_chunk and *elevation* from elevation_chunk to a CSV file.

    Args:
        file_path: The path to the CSV file where the elevation data will be stored.
        coord_chunk: A numpy array of node_id, lat, lon.
        elevation_chunk: A dictionary of locations (contains list of dictionaries of lat, lon, ele).
    """
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
    """Create temporary table and column in original table for elevations.
    
    Args:
        table_name_orig: Table where the node_ids and geoms are stored.
        table_name_dest: Temporary table where the elevations will be stored.
        schema: The database schema of where the tables are stored.
    """
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
    logger.info("Database is set up.")
    
def copy_csv_to_postgresql(schema: str, table_name: str, file_path: str):
    """Copy the CSV file with elevations to the PostgreSQL database.
    
    Args:
        schema: The database schema of where the table_name is stored.
        table_name: Table where the elevations will be stored.
        file_name: The path to the CSV file where the elevation data are stored.
    """
    copy_query = f"""
    COPY {schema}.{table_name} (node_id, elevation)
    FROM STDIN WITH CSV HEADER
    DELIMITER AS ','"""
    try:
        logger.info("Copying CSV with elevations to PostgreSQL database...")
        with get_connection() as conn:
            with conn.cursor() as cur:
                with open(file_path, 'r') as f:
                    cur.copy_expert(copy_query, f)
        conn.commit()
        logger.info("CSV with elevations successfully copied to PostgreSQL database.")
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")

def update_and_drop_table(table_name_orig: str, table_name_dest: str, schema: str, coords: np.ndarray):
    """Update the original table with elevations and drop the temporary table.
    
    Args:
        table_name_orig: Table where the node_ids and geoms are stored.
        table_name_dest: Temporary table where the elevations are stored.
        schema: The database schema of where the tables are stored.
        coords: A numpy array of node_id, lat, lon.
    """
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

def add_elevations(table_name_orig: str, table_name_dest: str, schema: str, file_path: str):
    """Add elevations to nodes in PostgreSQL database.

    Args:
        table_name_orig: Table where the node_ids and geoms are stored.
        table_name_dest: Temporary table where the elevations are stored.
        schema: The database schema of where the tables are stored.
        file_name: The path to the CSV file where the elevation data are stored.
    """
    setup_database(table_name_orig, table_name_dest, schema)
    coords = load_coords(table_name_orig, schema)
    process_chunks(file_path, coords)
    copy_csv_to_postgresql(schema, table_name_dest, file_path)
    # update_and_drop_table(table_name_orig, table_name_dest, schema, coords)

def time_function(func):
    """Decorator to time a function's execution."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger.info(f"The function {func.__name__} took {end - start} seconds to execute.")
        return result
    return wrapper

def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add elevations to nodes in PostgreSQL database.", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('table_name', help="The name of the table where the nodes data are stored.")
    parser.add_argument("-sch", "--schema", dest="schema", default="public", help="The database schema of the table where nodes are stored.")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Enable verbose output (DEBUG level logging)")
    parser.add_argument("-t", "--time", dest="time", action="store_true", help="Time the execution of add_elevations.")

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

    if args.time:
        timed_add_elevations = time_function(add_elevations)
        timed_add_elevations(table_name_orig, table_name_dest, schema, elevation_file)
    else:
        add_elevations(table_name_orig, table_name_dest, schema, elevation_file)

    if os.path.exists(elevation_file):
        os.remove(elevation_file)
        logger.info(f"Removed elevation file: {elevation_file}")
    else:
        logger.warning(f"Elevation file not found: {elevation_file}")

if __name__ == '__main__':
    main()
    # main(['nodes', '-sch', 'monaco'])
    # main(['nodes', '-sch', 'monaco', '-t'])
