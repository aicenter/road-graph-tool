import argparse
import os
from pathlib import Path
import subprocess
import logging
import stat

from sqlalchemy.sql.coercions import schema

import roadgraphtool.exec

from roadgraphtool.config import parse_config_file, get_path_from_config
from roadgraphtool.exceptions import InvalidInputError, MissingInputError, TableNotEmptyError, SubprocessError
from roadgraphtool.db import db
from roadgraphtool.schema import *
from scripts.filter_osm import load_multipolygon_by_id, is_valid_extension, setup_logger
from scripts.find_bbox import find_min_max

AREA_ID_SEQUENCE = "dataset_id_seq"

SQL_DIR = Path(__file__).parent.parent.parent / "SQL"

POSTPROCESS_DICT = {"pipeline.lua": "after_import.sql"}

logger = setup_logger('process_osm')


def extract_bbox(relation_id: int) -> tuple[float, float, float, float]:
    """Return tuple of floats based on bounding box coordinations."""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    logger.debug(f"Bounding box found: {min_lon},{min_lat},{max_lon},{max_lat}.")
    return min_lon, min_lat, max_lon, max_lat


def run_osmium_cmd(flag: str, input_file: str, output_file: Path = None):
    """Run osmium command based on flag."""
    if output_file and not is_valid_extension(output_file):
        raise InvalidInputError("File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    match flag:
        case "d":
            subprocess.run(["osmium", "show", input_file])
        case "i":
            subprocess.run(["osmium", "fileinfo", input_file])
        case "ie":
            subprocess.run(["osmium", "fileinfo", "-e", input_file])
        case 'r':
            res = subprocess.run(["osmium", "renumber", input_file, "-o", str(output_file)])
            if not res.returncode:
                logger.info("Renumbering of OSM data completed.")
        case 's':
            res = subprocess.run(["osmium", "sort", input_file, "-o", str(output_file)])
            if not res.returncode:
                logger.info("Sorting of OSM data completed.")
        case 'sr':
            tmp_file = 'tmp.osm'
            roadgraphtool.exec.call_executable(["osmium", "sort", input_file, "-o", tmp_file])
            # res = subprocess.run(["osmium", "sort", input_file, "-o", str(output_file)])
            logger.info("Sorting of OSM data completed.")
            roadgraphtool.exec.call_executable(["osmium", "renumber", tmp_file, "-o", str(output_file)])
            # res = subprocess.run(["osmium", "renumber", tmp_file, "-o", str(output_file)])
            logger.info("Renumbering of OSM data completed.")
            os.remove(tmp_file)


def setup_ssh_tunnel(config) -> int:
    """Set up SSH tunnel if needed and returns port number."""
    if hasattr(config, "server"):  # remote connection
        db.start_or_restart_ssh_connection_if_needed()
        config.db_server_port = db.ssh_tunnel_local_port
        return db.ssh_tunnel_local_port
    # local connection
    return config.db_server_port

def setup_pgpass(config):
    """Create pgpass file or rewrite its content.

    WARNING: This method should be called before connecting to the database
    and file should be removed after the connection is closed - use remove_pgpass() method.
    """
    db_config = config.db
    pgpass_config_path = Path(config.importer.pgpass_file).expanduser().resolve()

    # hostname:port:database:username:password
    content = f"{db_config.db_host}:{db_config.db_server_port}:{db_config.db_name}:{db_config.username}:{db_config.db_password}"
    with open(pgpass_config_path, 'w') as pgfile:
        pgfile.write(content)
    os.chmod(pgpass_config_path, stat.S_IRUSR | stat.S_IWUSR)
    os.environ['PGPASSFILE'] = str(pgpass_config_path)
    logging.info(f"Created pgpass file: {pgpass_config_path}")

def remove_pgpass(config):
    """Remove pgpass file if exists."""
    pgpass_config_path = config.importer.pgpass_file

    if os.path.exists(pgpass_config_path):
        os.remove(pgpass_config_path)
        logging.info(f"Removed pgpass file: {pgpass_config_path}")


def run_osm2pgsql_cmd(
    config,
    coords: str | list[int] = None
):
    """
    Import data from input_file to database specified in config using osm2pgsql tool.

    Parameters:
        config: configuration
    """

    importer_config = config.importer
    schema = importer_config.schema
    pgpass = importer_config.pgpass

    db_config = config.db

    if hasattr(db_config, "ssh"):
        port = setup_ssh_tunnel(config)
    else:
        port =  db_config.db_server_port
    logger.debug(f"Port is: {port}")

    if not importer_config.force and not check_empty_or_nonexistent_tables(schema):
        raise TableNotEmptyError("Attempt to overwrite non-empty tables. Use 'force: true' in config.importer to proceed.")

    create_schema(schema)
    add_postgis_extension(schema)

    connection_uri = f"postgresql://{db_config.username}@{db_config.db_host}:{port}/{db_config.db_name}"
    cmd = ["osm2pgsql", "-d", connection_uri, "--output=flex", "-S", str(importer_config.style_file), str(importer_config.input_file), "-x", f"--schema={schema}"]
    if coords:
        cmd.extend(["-b", coords])

    if logger.level == logging.DEBUG:
        cmd.extend(['--log-level=debug'])

    if not pgpass:
        cmd.extend(["-W"])

    logger.info(f"Begin importing...")
    logger.debug(' '.join(cmd))

    if pgpass:
        logger.info("Setting up pgpass file...")
        setup_pgpass(config)
    try:
        res = roadgraphtool.exec.call_executable(cmd, output_type=roadgraphtool.exec.ReturnContent.EXIT_CODE)
    finally:
        if pgpass:
            logger.info("Deleting pgpass file...")
            remove_pgpass(config)
    if res:
        raise SubprocessError(f"Error during import: {res}")

    logger.info("Importing completed.")
    
def postprocess_osm_import_old(config):
    """Apply postprocessing SQL associated with **style_file_path** to data in **schema** after importing.
    """
    style_file_path = os.path.basename(config.importer.style_file)
    db_config = config.db

    if style_file_path in POSTPROCESS_DICT:
        sql_file_path = str(SQL_DIR / POSTPROCESS_DICT[style_file_path])
        cmd = ["psql", "-d", db_config.db_name, "-U", db_config.username, "-h", db_config.db_host, "-p",
                str(db_config.db_server_port), "-c", f"SET search_path TO {schema};", "-f", sql_file_path]

        logger.info("Post-processing OSM data after import...")
        logger.debug(' '.join(cmd))

        res = roadgraphtool.exec.call_executable(cmd)

        if res:
            raise SubprocessError(f"Error during post-processing: {res}")
        logger.info("Post-processing completed.")
    else:
        logger.warning(f"No post-processing defined for style {style_file_path}")


def import_osm_to_db(config):
#def import_osm_to_db(args):
    """Renumber IDs of OSM objects and sorts file by them, import the new file to database specified in config.ini file.

    The **pipeline.lua** style file is used if not specified or set otherwise. Default schema is **public**.
    """

    importer_config = config.importer
    input_file_path = get_path_from_config(config, importer_config.input_file)
    style_file_path = get_path_from_config(config, importer_config.style_file)

    if not os.path.exists(input_file_path) or not is_valid_extension(input_file_path):
        raise FileNotFoundError("No valid file to import was found.")

    if not os.path.exists(args.style_file):
        raise FileNotFoundError(f"Style file {args.style_file_path} does not exist.")

    try:
        # importing to database
        run_osm2pgsql_cmd(config)

        port = setup_ssh_tunnel(config)
        postprocess_osm_import(config)

        postprocess_osm_import(args)
        # postprocess_osm_import(CREDENTIALS, style_file_path, schema)
    except SubprocessError as e:
        logger.error(f"Error during processing: {e}")


def check_and_print_warning(overlaps: dict[str, list[tuple]]):
    for (element_type, overlap) in overlaps.items():
        if overlap:
            logger.warning(f"{overlap} {element_type} with the same ID are already in the database and not added.")
    pass


def postprocess_osm_import(args):
    try:
        with get_connection() as connection:

            schema = args.schema
            target_schema = args.target_schema

            area_id = create_area(connection, target_schema, args.input_file, args.area_name)

            overlaps = {}
            overlaps['nodes'] = get_overlapping_elements(connection, schema, target_schema, 'nodes')
            overlaps['ways'] = get_overlapping_elements(connection, schema, target_schema, 'ways')
            overlaps['relations'] = get_overlapping_elements(connection, schema, target_schema, 'relations')

            check_and_print_warning(overlaps)

            copy_nodes(connection, schema, target_schema, area_id)
            copy_ways(connection, schema, target_schema, area_id)
            copy_relations(connection, schema, target_schema, area_id)
            copy_nodes_ways(connection, schema, target_schema, area_id)

            return area_id
    except (psycopg2.DatabaseError, Exception) as error:
        raise Exception(f"Error: {str(error)}")


def generate_area_id(connection, target_schema):
    with connection.cursor() as cursor:
        query = f'''
                SELECT nextval('"{target_schema}"."{AREA_ID_SEQUENCE}"') 
'''
        cursor.execute(query)
        return cursor.fetchone()[0]


def create_area(connection, target_schema: str, input_file: str, area_name: str):
    # TODO: add geom
    area_id = generate_area_id(connection, target_schema)
    with connection.cursor() as cursor:
        query = f'''
                INSERT INTO "{target_schema}".areas (id, "name", description)
                VALUES ({area_id},'{area_name}','{input_file}') '''
        cursor.execute(query)
        connection.commit()

    return area_id


def copy_nodes(connection, import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying nodes")
    with connection.cursor() as cursor:
        query = f'''
                INSERT INTO "{target_schema}".nodes (id,tags,geom, area)
                SELECT id, tags, geom, {area_id}
                FROM "{import_schema}".nodes i
                WHERE NOT EXISTS
                    (SELECT id
                        FROM "{target_schema}".nodes e
                        WHERE i.id = e.id)'''

        logger.debug(f'Executing following SQL: {query}')
        cursor.execute(query)
        logger.debug(f'Inserted rows: {cursor.rowcount}')
        connection.commit()


def copy_nodes_ways(connection, import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying nodes ways")
    with connection.cursor() as cursor:
        query = f'''
                INSERT INTO "{target_schema}".nodes_ways (way_id,node_id,"position",area)
                SELECT way_id,node_id,"position", {area_id}
                FROM "{import_schema}".nodes_ways i
                WHERE EXISTS
                    (SELECT id
                        FROM "{target_schema}".ways e
                        WHERE i.way_id = e.id AND e.area = {area_id})'''
        # query = f'''
        #         INSERT INTO "{target_schema}".nodes_ways (way_id,node_id,"position",area)
        #         SELECT way_id,node_id,"position", {area_id}
        #         FROM "{import_schema}".nodes_ways i'''
        logger.debug(f'Executing following SQL: {query}')
        cursor.execute(query)
        logger.debug(f'Inserted rows: {cursor.rowcount}')
        connection.commit()


def copy_ways(connection, import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying ways")
    with connection.cursor() as cursor:
        query = f'''
                INSERT INTO "{target_schema}".ways (id, tags, geom,"from","to", oneway, area)
                SELECT id, tags, geom,"from","to", oneway, {area_id}
                FROM "{import_schema}".ways i
                WHERE NOT EXISTS
                    (SELECT id
                        FROM "{target_schema}".ways e
                        WHERE i.id = e.id)'''
        logger.debug(f'Executing following SQL: {query}')
        cursor.execute(query)
        logger.debug(f'Inserted rows: {cursor.rowcount}')
        connection.commit()


def copy_relations(connection, import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying relations")
    with connection.cursor() as cursor:
        query = f'''
                INSERT INTO "{target_schema}".relations (id,tags,members, area)
                SELECT id, tags, members, {area_id}
                FROM "{import_schema}".relations i
                WHERE NOT EXISTS
                    (SELECT id
                        FROM "{target_schema}".relations e
                        WHERE i.id = e.id)'''
        logger.debug(f'Executing following SQL: {query}')
        cursor.execute(query)
        logger.debug(f'Inserted rows: {cursor.rowcount}')
        connection.commit()


def get_overlapping_elements(connection, schema: str, target_schema: str, table_name: str):
    with connection.cursor() as cursor:
        query = f'''
        SELECT count(*) FROM (
                SELECT id 
                FROM "{schema}"."{table_name}" i
                WHERE EXISTS
                    (SELECT id
                    FROM "{target_schema}"."{table_name}" e
                    WHERE i.id = e.id));'''
        cursor.execute(query)
        return cursor.fetchone()[0]


def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process OSM files and interact with PostgreSQL database.",
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("flag", choices=["d", "i", "ie", "s", "r", "sr", "b", "u"], metavar="flag",
                        help="""
d  : Display OSM file
i  : Display information about OSM file
ie : Display extended information about OSM file
s  : Sort OSM file based on IDs
r  : Renumber object IDs in OSM file
sr : Sort and renumber objects in OSM file
u  : Preprocess and upload OSM file to PostgreSQL database using osm2pgsql
b  : Extract greatest bounding box from given relation ID of 
     input_file and upload to PostgreSQL database using osm2pgsql"""
                        )
    parser.add_argument('input_file', help="Path to input OSM file")
    parser.add_argument("-id", dest="relation_id", help="Relation ID (required for 'b' flag)")
    parser.add_argument("-l", dest="style_file", nargs='?', help=f"Path to style file (optional for 'b', 'u' flag) - default is 'pipeline.lua'")
                        help=f"Path to style file (optional for 'b', 'u' flag) - default is '{DEFAULT_STYLE_FILE}'")
    parser.add_argument("-o", dest="output_file", help="Path to output file (required for 's', 'r', 'sr' flag)")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Enable verbose output (DEBUG level logging)")
    parser.add_argument("-sch", "--schema", dest="schema", default="public",
                        help="Specify dabatabse schema (for 'b', 'u' flag) - default is 'public'")
    parser.add_argument("--force", dest="force", action="store_true", help="Force overwrite of data in existing tables in schema (for 'b', 'u' flag)")
    parser.add_argument("-P", dest="pgpass", action="store_true", help="Force using pgpass file instead of password prompt (for 'b', 'u' flag)")

    args = parser.parse_args(arg_list)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return args


