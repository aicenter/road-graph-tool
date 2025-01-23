import json
import logging
import os
import stat
import subprocess
from pathlib import Path
from importlib.resources import files

from roadgraphtool.insert_area import insert_area, read_json_file
from sqlalchemy.sql.coercions import schema

import roadgraphtool.exec
from roadgraphtool.insert_area import insert_area
from roadgraphtool.config import get_path_from_config
from roadgraphtool.db import db
from roadgraphtool.exceptions import InvalidInputError, TableNotEmptyError, SubprocessError
from roadgraphtool.schema import *
from scripts.filter_osm import load_multipolygon_by_id, is_valid_extension, setup_logger
from scripts.find_bbox import find_min_max

AREA_ID_SEQUENCE = "dataset_id_seq"

SQL_DIR = Path(__file__).parent.parent.parent / "SQL"

postprocess_dict = {"pipeline": "after_import.sql"}

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
    style_file_path: Path,
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
    cmd = ["osm2pgsql", "-d", connection_uri, "--output=flex", "-S", str(style_file_path), str(importer_config.input_file), "-x", f"--schema={schema}"]
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
    db_config = config.db

    if config.importer.style_file in postprocess_dict:
        sql_file_path = str(SQL_DIR / postprocess_dict[config.importer.style_file])
        cmd = ["psql", "-d", db_config.db_name, "-U", db_config.username, "-h", db_config.db_host, "-p",
                str(db_config.db_server_port), "-c", f"SET search_path TO {schema};", "-f", sql_file_path]

        logger.info("Post-processing OSM data after import...")
        logger.debug(' '.join(cmd))

        res = roadgraphtool.exec.call_executable(cmd)

        if res:
            raise SubprocessError(f"Error during post-processing: {res}")
        logger.info("Post-processing completed.")
    else:
        logger.warning(f"No post-processing defined for style {config.importer.style_file}")


def import_osm_to_db(config) -> int:
    """Renumber IDs of OSM objects and sorts file by them, import the new file to database specified in config.ini file.
    The **pipeline.lua** style file is used if not specified or set otherwise. Default schema is **public**.
    """

    importer_config = config.importer
    input_file_path = get_path_from_config(config, importer_config.input_file)

    if not input_file_path.exists() or not is_valid_extension(input_file_path):
        raise FileNotFoundError("No valid file to import was found.")

    # custom style file
    if config.importer.style_file.endswith('.lua'):
        style_file_path = get_path_from_config(config, importer_config.style_file)

        if not style_file_path.exists():
            raise FileNotFoundError(f"Style file {config.importer.style_file} does not exist.")
    # predefined style file
    else:
        resources_path = "roadgraphtool.resources"
        style_file_path = files(resources_path).joinpath(f"lua_styles/{config.importer.style_file}.lua")
    try:
        # importing to database
        run_osm2pgsql_cmd(config, style_file_path)

        # postprocessing
        area_id = postprocess_osm_import(config)
        return area_id
        # postprocess_osm_import(config)
    except SubprocessError as e:
        logger.error(f"Error during processing.")
        # logger.error(f"Error during processing: {e}")


def check_and_print_warning(overlaps: dict[str, int]):
    for (element_type, overlap) in overlaps.items():
        if overlap:
            logger.warning(f"{overlap} {element_type} with the same ID are already in the database and not added.")
    pass


def postprocess_osm_import(config):
    schema = config.importer.schema
    target_schema = config.schema

    # set schema to target schema
    db.execute_sql(f"SET search_path TO {target_schema},public;")

    description = f"Imported from {config.importer.input_file}"

    # area creation
    args = {}
    if hasattr(config.importer, 'geom'):
        geom_path = read_json_file(config.importer.geom)
        args['geom'] = geom_path
    area_id = insert_area(**args, name=config.importer.area_name, description=description)

    overlaps = {}
    overlaps['nodes'] = get_overlapping_elements_count(schema, target_schema, 'nodes')
    overlaps['ways'] = get_overlapping_elements_count(schema, target_schema, 'ways')
    overlaps['relations'] = get_overlapping_elements_count(schema, target_schema, 'relations')

    check_and_print_warning(overlaps)

    copy_nodes(schema, target_schema, area_id)
    copy_ways(schema, target_schema, area_id)
    copy_relations(schema, target_schema, area_id)
    copy_nodes_ways(schema, target_schema, area_id)

    return area_id

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


def copy_nodes(import_schema: str, target_schema: str, area_id: int):
    assert isinstance(area_id, int)

    logger.debug("Copying nodes")
    query = f'''
        INSERT INTO "{target_schema}".nodes (id,tags,geom, area)
        SELECT id, tags, geom, {area_id}
        FROM "{import_schema}".nodes i
        WHERE NOT EXISTS
            (SELECT id
                FROM "{target_schema}".nodes e
                WHERE i.id = e.id)'''

    logger.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logger.debug(f'Inserted rows: {result.rowcount}')


def copy_nodes_ways(import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying nodes ways")
    query = f'''
            INSERT INTO "{target_schema}".nodes_ways (way_id,node_id,"position",area)
            SELECT way_id,node_id,"position", {area_id}
            FROM "{import_schema}".nodes_ways i
            WHERE EXISTS
                (SELECT id
                    FROM "{target_schema}".ways e
                    WHERE i.way_id = e.id AND e.area = {area_id})'''
    logger.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logger.debug(f'Inserted rows: {result.rowcount}')


def copy_ways(import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying ways")
    query = f'''
            INSERT INTO "{target_schema}".ways (id, tags, geom,"from","to", oneway, area)
            SELECT id, tags, geom,"from","to", oneway, {area_id}
            FROM "{import_schema}".ways i
            WHERE NOT EXISTS
                (SELECT id
                    FROM "{target_schema}".ways e
                    WHERE i.id = e.id)'''
    logger.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logger.debug(f'Inserted rows: {result.rowcount}')


def copy_relations(import_schema: str, target_schema: str, area_id: int):
    logger.debug("Copying relations")
    query = f'''
            INSERT INTO "{target_schema}".relations (id,tags,members, area)
            SELECT id, tags, members, {area_id}
            FROM "{import_schema}".relations i
            WHERE NOT EXISTS
                (SELECT id
                    FROM "{target_schema}".relations e
                    WHERE i.id = e.id)'''
    logger.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logger.debug(f'Inserted rows: {result.rowcount}')


def get_overlapping_elements_count(schema: str, target_schema: str, table_name: str):
    query = f'''
        SELECT count(*) FROM (
                SELECT id 
                FROM "{schema}"."{table_name}" i
                WHERE EXISTS
                    (SELECT id
                    FROM "{target_schema}"."{table_name}" e
                    WHERE i.id = e.id)) as sub;'''
    return db.execute_count_query(query)


