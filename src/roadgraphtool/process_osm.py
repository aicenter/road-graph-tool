import logging
import os
import stat
import subprocess
from pathlib import Path
from typing import Optional

import roadgraphtool.exec
from roadgraphtool.config import get_path_from_config
from roadgraphtool.db import db
from roadgraphtool.exceptions import InvalidInputError, TableNotEmptyError, SubprocessError
from roadgraphtool.insert_area import genereate_area
from roadgraphtool.schema import *
from roadgraphtool.filter_osm import load_multipolygon_by_id, is_valid_extension
from roadgraphtool.find_bbox import find_min_max

import shapely
import shapely.geometry as geometry

AREA_ID_SEQUENCE = "areas_id_seq"

SQL_DIR = Path(__file__).parent.parent.parent / "SQL"

postprocess_dict = {"pipeline": "after_import.sql"}


def _ri_source(config):
    return config.road_import.source


def _ri_schema(config):
    return config.road_import.schema


def _bbox_string_from_geom(geom) -> str:
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    return f"{min_lon},{min_lat},{max_lon},{max_lat}"


def extract_bbox(relation_id: int) -> tuple[float, float, float, float]:
    """Return tuple of floats based on bounding box coordinations."""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    logging.debug(f"Bounding box found: {min_lon},{min_lat},{max_lon},{max_lat}.")
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
                logging.info("Renumbering of OSM data completed.")
        case 's':
            res = subprocess.run(["osmium", "sort", input_file, "-o", str(output_file)])
            if not res.returncode:
                logging.info("Sorting of OSM data completed.")
        case 'sr':
            tmp_file = 'tmp.osm'
            roadgraphtool.exec.call_executable(["osmium", "sort", input_file, "-o", tmp_file])
            logging.info("Sorting of OSM data completed.")
            roadgraphtool.exec.call_executable(["osmium", "renumber", tmp_file, "-o", str(output_file)])
            logging.info("Renumbering of OSM data completed.")
            os.remove(tmp_file)


def setup_ssh_tunnel(config) -> int:
    """Set up SSH tunnel if needed and returns port number."""
    if hasattr(config, "server"):  # remote connection
        db._start_or_restart_ssh_connection_if_needed()
        config.db_server_port = db.ssh_tunnel_local_port
        return db.ssh_tunnel_local_port
    return config.db.db_server_port


def setup_pgpass(config):
    """Create pgpass file or rewrite its content.

    WARNING: This method should be called before connecting to the database
    and file should be removed after the connection is closed - use remove_pgpass() method.
    """
    db_config = config.db
    pgpass_config_path = Path(_ri_source(config).pgpass_file).expanduser().resolve()

    if hasattr(db_config, "ssh"):
        port = db_config.ssh.tunnel_port
    else:
        port = db_config.db_server_port

    content = f"{db_config.db_host}:{port}:{db_config.db_name}:{db_config.username}:{db_config.db_password}"
    with open(pgpass_config_path, 'w') as pgfile:
        pgfile.write(content)
    os.chmod(pgpass_config_path, stat.S_IRUSR | stat.S_IWUSR)
    os.environ['PGPASSFILE'] = str(pgpass_config_path)
    logging.info(f"Created pgpass file: {pgpass_config_path}")


def remove_pgpass(config):
    """Remove pgpass file if exists."""
    pgpass_config_path = _ri_source(config).pgpass_file

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
        config: configuration with ``road_import`` section
    """
    source = _ri_source(config)
    schema = _ri_schema(config)
    pgpass = source.pgpass

    db_config = config.db

    port = db.db_server_port
    logging.debug(f"Port is: {port}")

    input_path = get_path_from_config(config, source.input_file)

    if not source.force and not check_empty_or_nonexistent_tables(schema):
        raise TableNotEmptyError(
            "Attempt to overwrite non-empty tables. Use 'force: true' in road_import.source to proceed."
        )

    connection_uri = f"postgresql://{db_config.username}@{db_config.db_host}:{port}/{db_config.db_name}"
    cmd = [
        "osm2pgsql", "-d", connection_uri, "--output=flex", "-S", f'{style_file_path}',
        str(input_path), "-x", f"--schema={schema}"
    ]
    if coords:
        cmd.extend(["-b", coords])

    if logging.root.level == logging.DEBUG:
        cmd.extend(['--log-level=debug'])

    if not pgpass:
        cmd.extend(["-W"])

    logging.info(f"Begin importing...")
    logging.debug(' '.join(cmd))

    if pgpass:
        logging.info("Setting up pgpass file...")
        setup_pgpass(config)
    try:
        res = roadgraphtool.exec.call_executable(cmd, output_type=roadgraphtool.exec.ReturnContent.EXIT_CODE)
    finally:
        if pgpass:
            logging.info("Deleting pgpass file...")
            remove_pgpass(config)
    if res:
        raise SubprocessError(f"Error during import: {res}")

    logging.info("Importing completed.")


def postprocess_osm_import_old(config):
    """Apply postprocessing SQL associated with **style_file_path** to data in **schema** after importing.
    """
    db_config = config.db
    staging = _ri_schema(config)
    style_key = _ri_source(config).style_file
    if style_key in postprocess_dict:
        sql_file_path = str(SQL_DIR / postprocess_dict[style_key])
        cmd = ["psql", "-d", db_config.db_name, "-U", db_config.username, "-h", db_config.db_host, "-p",
               str(db_config.db_server_port), "-c", f"SET search_path TO {staging};", "-f", sql_file_path]

        logging.info("Post-processing OSM data after import...")
        logging.debug(' '.join(cmd))

        res = roadgraphtool.exec.call_executable(cmd)

        if res:
            raise SubprocessError(f"Error during post-processing: {res}")
        logging.info("Post-processing completed.")
    else:
        logging.warning(f"No post-processing defined for style {style_key}")


def _create_area_from_import(config) -> int:
    description = f"Imported from {_ri_source(config).input_file}"
    return genereate_area(config, description)


def postprocess_osm_import(config, existing_area_id: Optional[int] = None) -> int:
    schema = _ri_schema(config)
    target_schema = config.schema

    db.execute_sql(f"SET search_path TO {target_schema},public;")

    if existing_area_id is not None:
        area_id = existing_area_id
    else:
        area_id = _create_area_from_import(config)

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


def _run_osm_file_backend(config, area_id: Optional[int]) -> int:
    """Import OSM via osm2pgsql; optionally clip to the bbox of *area_id*'s polygon in DB."""
    source = _ri_source(config)
    input_file_path = get_path_from_config(config, source.input_file)

    if not input_file_path.exists() or not is_valid_extension(input_file_path):
        raise FileNotFoundError("No valid file to import was found.")

    if source.style_file.endswith('.lua'):
        style_file_path = get_path_from_config(config, source.style_file)
        if not style_file_path.exists():
            raise FileNotFoundError(f"Style file {source.style_file} does not exist.")
    else:
        style_file_path = Path(__file__).resolve().parent.parent.parent / f"lua_styles/{source.style_file}.lua"

    coords = None
    if area_id is not None:
        from roadgraphtool.road_import import get_area_polygon

        poly = get_area_polygon(config, area_id)
        if poly is None:
            raise ValueError(
                f"No geometry found for area id {area_id} in schema {config.schema}.areas "
                "(required when road import runs with an area_id)."
            )
        coords = _bbox_string_from_geom(poly)
        logging.info("Using bbox from area polygon for osm2pgsql: %s", coords)

    try:
        create_schema(_ri_schema(config))
        add_postgis_extension(_ri_schema(config))

        logging.info("Importing OSM data to database")
        run_osm2pgsql_cmd(config, style_file_path, coords=coords)

        logging.info("Post-processing OSM data in database")
        return postprocess_osm_import(config, existing_area_id=area_id)
    except SubprocessError:
        logging.error("Error during processing.")
        raise


def import_osm_to_db(config) -> int:
    """Import OSM file and create a new area (no pre-existing *area_id*). Same as pipeline osm_file without area."""
    return _run_osm_file_backend(config, area_id=None)


def check_and_print_warning(overlaps: dict[str, int]):
    for (element_type, overlap) in overlaps.items():
        if overlap:
            logging.warning(f"{overlap} {element_type} with the same ID are already in the database and not added.")


def generate_area_id(connection, target_schema):
    with connection.cursor() as cursor:
        query = f'''
                SELECT nextval('"{target_schema}"."{AREA_ID_SEQUENCE}"') 
'''
        cursor.execute(query)
        return cursor.fetchone()[0]


def create_area(connection, target_schema: str, input_file: str, area_name: str, geom: shapely.Geometry):
    area_id = generate_area_id(connection, target_schema)
    with connection.cursor() as cursor:
        if geom:
            query = f'''
                INSERT INTO "{target_schema}".areas (id, "name", description, geom)
                VALUES ({area_id},'{area_name}','{input_file}','ST_GeomFromWKB
(decode({shapely.to_wkb(geom, hex=True)},'hex')') '''
        else:
            query = f'''
                INSERT INTO "{target_schema}".areas (id, "name", description)
                VALUES ({area_id},'{area_name}','{input_file}') '''

        cursor.execute(query)
        connection.commit()

    return area_id


def copy_nodes(import_schema: str, target_schema: str, area_id: int):
    assert isinstance(area_id, int)

    logging.debug("Copying nodes")
    query = f'''
        INSERT INTO "{target_schema}".nodes (id,tags,geom, area)
        SELECT id, tags, geom, {area_id}
        FROM "{import_schema}".nodes i
        WHERE NOT EXISTS
            (SELECT id
                FROM "{target_schema}".nodes e
                WHERE i.id = e.id)'''

    logging.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logging.debug(f'Inserted rows: {result.rowcount}')


def copy_nodes_ways(import_schema: str, target_schema: str, area_id: int):
    logging.debug("Copying nodes ways")
    query = f'''
            INSERT INTO "{target_schema}".nodes_ways (way_id,node_id,"position",area)
            SELECT way_id,node_id,"position", {area_id}
            FROM "{import_schema}".nodes_ways i
            WHERE EXISTS
                (SELECT id
                    FROM "{target_schema}".ways e
                    WHERE i.way_id = e.id AND e.area = {area_id})'''
    logging.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logging.debug(f'Inserted rows: {result.rowcount}')


def copy_ways(import_schema: str, target_schema: str, area_id: int):
    logging.debug("Copying ways")
    query = f'''
            INSERT INTO "{target_schema}".ways (id, tags, geom,"from","to", oneway, area)
            SELECT id, tags, geom,"from","to", oneway, {area_id}
            FROM "{import_schema}".ways i
            WHERE NOT EXISTS
                (SELECT id
                    FROM "{target_schema}".ways e
                    WHERE i.id = e.id)'''
    logging.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logging.debug(f'Inserted rows: {result.rowcount}')


def copy_relations(import_schema: str, target_schema: str, area_id: int):
    logging.debug("Copying relations")
    query = f'''
            INSERT INTO "{target_schema}".relations (id,tags,members, area)
            SELECT id, tags, members, {area_id}
            FROM "{import_schema}".relations i
            WHERE NOT EXISTS
                (SELECT id
                    FROM "{target_schema}".relations e
                    WHERE i.id = e.id)'''
    logging.debug(f'Executing following SQL: {query}')
    result = db.execute_sql(query)
    logging.debug(f'Inserted rows: {result.rowcount}')


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
