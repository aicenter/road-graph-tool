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

SQL_DIR = Path(__file__).parent.parent.parent / "SQL"

POSTPROCESS_DICT = {"pipeline.lua": "after_import.sql"}

logger = setup_logger('process_osm')

def extract_bbox(relation_id: int) -> tuple[float, float, float, float]:
    """Return tuple of floats based on bounding box coordinations."""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    logger.debug(f"Bounding box found: {min_lon},{min_lat},{max_lon},{max_lat}.")
    return min_lon, min_lat, max_lon, max_lat

def run_osmium_cmd(flag: str, input_file: str, output_file: str = None):
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
            res = subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
            if not res.returncode:
                logger.info("Renumbering of OSM data completed.")
        case 's':
            res = subprocess.run(["osmium", "sort", input_file, "-o", output_file])
            if not res.returncode:
                logger.info("Sorting of OSM data completed.")
        case 'sr':
            tmp_file = 'tmp.osm'
            res = subprocess.run(["osmium", "sort", input_file, "-o", tmp_file])
            if not res.returncode:
                logger.info("Sorting of OSM data completed.")
                res = subprocess.run(["osmium", "renumber", tmp_file, "-o", output_file])
                if not res.returncode:
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
    cmd = ["osm2pgsql", "-d", connection_uri, "--output=flex", "-S", importer_config.style_file, str(importer_config.input_file), "-x", f"--schema={schema}"]
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

def postprocess_osm_import(config):
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
    """Renumber IDs of OSM objects and sorts file by them, import the new file to database specified in config.ini file.

    The **pipeline.lua** style file is used if not specified or set otherwise. Default schema is **public**.
    """

    importer_config = config.importer
    input_file_path = get_path_from_config(config, importer_config.input_file)
    style_file_path = get_path_from_config(config, importer_config.style_file)

    if not os.path.exists(input_file_path) or not is_valid_extension(input_file_path):
        raise FileNotFoundError("No valid file to import was found.")

    if not os.path.exists(style_file_path):
        raise FileNotFoundError(f"Style file {style_file_path} does not exist.")

    try:
        # importing to database
        run_osm2pgsql_cmd(config)

        # postprocessing
        postprocess_osm_import(config)
    except SubprocessError as e:
        logger.error(f"Error during processing: {e}")



def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process OSM files and interact with PostgreSQL database.", formatter_class=argparse.RawTextHelpFormatter)

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
    parser.add_argument("-o", dest="output_file", help="Path to output file (required for 's', 'r', 'sr' flag)")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Enable verbose output (DEBUG level logging)")
    parser.add_argument("-sch", "--schema", dest="schema", default="public", help="Specify dabatabse schema (for 'b', 'u' flag) - default is 'public'")
    parser.add_argument("--force", dest="force", action="store_true", help="Force overwrite of data in existing tables in schema (for 'b', 'u' flag)")
    parser.add_argument("-P", dest="pgpass", action="store_true", help="Force using pgpass file instead of password prompt (for 'b', 'u' flag)")

    args = parser.parse_args(arg_list)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return args

def main(arg_list: list[str] | None = None):
    if arg_list is None:
        logging.error("You have to provide a path to the config file as an argument.")
        return -1

    config = parse_config_file(arg_list[0])
    importer_config = config.importer

    if not os.path.exists(config.input_file):
        raise FileNotFoundError(f"File '{importer_config.input_file}' does not exist.")
    elif not is_valid_extension(importer_config.input_file):
        raise InvalidInputError("File must have one of the following extensions: osm, osm.pbf, osm.bz2.")
    elif importer_config.style_file:
        if not os.path.exists(importer_config.style_file):
            raise FileNotFoundError(f"File '{importer_config.style_file}' does not exist.")
        elif not str(importer_config.style_file).endswith(".lua"):
            raise InvalidInputError("File must have the '.lua' extension.")
    
    match importer_config.flag:
        case 'd' | 'i' | 'ie':
            # Display content or (extended) information of OSM file
            run_osmium_cmd(importer_config.flag, importer_config.input_file)

        case 's' | 'r' | 'sr':
            # Sort, renumber OSM file or do both
            if not importer_config.output_file:
                raise MissingInputError("An output file must be specified with '-o' flag.")
            run_osmium_cmd(importer_config.flag, importer_config.input_file, importer_config.output_file)
    
        case "u":
            # Preprocess and upload OSM file to PostgreSQL database and then postprocess the data
            import_osm_to_db(importer_config.input_file, importer_config.force, importer_config.pgpass, importer_config.style_file, importer_config.schema)

        case "b":
            # Extract bounding box based on relation ID and import to PostgreSQL
            if not importer_config.relation_id:
                raise MissingInputError("Existing relation ID must be specified.")

            min_lon, min_lat, max_lon, max_lat = extract_bbox(importer_config.relation_id)
            coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            run_osm2pgsql_cmd(config.db, importer_config.input_file, importer_config.style_file, config.schema, importer_config.force, importer_config.pgpass, coords)
    
if __name__ == '__main__':
    main()
