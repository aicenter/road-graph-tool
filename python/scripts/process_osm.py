import argparse
import os
from pathlib import Path
import subprocess
import logging

from roadgraphtool.credentials_config import CREDENTIALS, CredentialsConfig
from roadgraphtool.exceptions import InvalidInputError, MissingInputError, TableNotEmptyError, SubprocessError
from roadgraphtool.db import db
from roadgraphtool.schema import *
from scripts.filter_osm import load_multipolygon_by_id, is_valid_extension, setup_logger, RESOURCES_DIR
from scripts.find_bbox import find_min_max

DEFAULT_STYLE_FILE = "pipeline.lua"
SQL_DIR = Path(__file__).parent.parent.parent / "SQL"
STYLES_DIR = RESOURCES_DIR / "lua_styles"
DEFAULT_STYLE_FILE_PATH = STYLES_DIR / DEFAULT_STYLE_FILE

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

def setup_ssh_tunnel(config: CredentialsConfig) -> int:
    """Set up SSH tunnel if needed and returns port number."""
    if hasattr(config, "server"):  # remote connection
        db.start_or_restart_ssh_connection_if_needed()
        config.db_server_port = db.ssh_tunnel_local_port
        return db.ssh_tunnel_local_port
    # local connection
    return config.db_server_port

def run_osm2pgsql_cmd(config: CredentialsConfig, input_file: str, style_file_path: str, schema: str, force: bool, pgpass: bool, coords: str| list[int] = None):
    """Import data from input_file to database specified in config using osm2pgsql tool."""

    port = setup_ssh_tunnel(config)
    logger.debug(f"Port is: {port}")

    if not force and not check_empty_or_nonexistent_tables(schema):
        raise TableNotEmptyError("Attempt to overwrite non-empty tables. Use '--force' flag to proceed.")

    create_schema(schema)
    add_postgis_extension(schema)

    connection_uri = f"postgresql://{config.username}@{config.db_host}:{port}/{config.db_name}"
    cmd = ["osm2pgsql", "-d", connection_uri, "--output=flex", "-S", style_file_path, input_file, "-x", f"--schema={schema}"]
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
        config.setup_pgpass()
    
    res = subprocess.run(cmd).returncode
    
    if pgpass:
        logger.info("Deleting pgpass file...")
        config.remove_pgpass()

    if res:
        raise SubprocessError(f"Error during import: {res}")
    logger.info("Importing completed.")

def postprocess_osm_import(config: CredentialsConfig, style_file_path: str, schema: str):
    """Apply postprocessing SQL associated with **style_file_path** to data in **schema** after importing.
    """
    style_file_path = os.path.basename(style_file_path)
    
    if style_file_path in POSTPROCESS_DICT:
        sql_file_path = str(SQL_DIR / POSTPROCESS_DICT[style_file_path])
        cmd = ["psql", "-d", config.db_name, "-U", config.username, "-h", config.db_host, "-p", 
                str(config.db_server_port), "-c", f"SET search_path TO {schema};", "-f", sql_file_path]

        logger.info("Post-processing OSM data after import...")
        logger.debug(' '.join(cmd))
        res = subprocess.run(cmd).returncode

        if res:
            raise SubprocessError(f"Error during post-processing: {res}")
        logger.info("Post-processing completed.")
    else:
        logger.warning(f"No post-processing defined for style {style_file_path}")

def import_osm_to_db(input_file: str, force: bool, pgpass: bool, style_file_path: str = str(DEFAULT_STYLE_FILE_PATH), schema: str = "public"):
    """Renumber IDs of OSM objects and sorts file by them, import the new file to database specified in config.ini file.

    The **pipeline.lua** style file is used if not specified or set otherwise. Default schema is **public**.
    """
    if not os.path.exists(input_file) or not is_valid_extension(input_file):
        raise FileNotFoundError("No valid file to import was found.")

    if not os.path.exists(style_file_path):
        raise FileNotFoundError(f"Style file {style_file_path} does not exist.")

    try:
        # importing to database
        run_osm2pgsql_cmd(CREDENTIALS, input_file, style_file_path, schema, force, pgpass)

        # postprocessing
        postprocess_osm_import(CREDENTIALS, style_file_path, schema)
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
    parser.add_argument("-l", dest="style_file", nargs='?', default=str(DEFAULT_STYLE_FILE_PATH), help=f"Path to style file (optional for 'b', 'u' flag) - default is '{DEFAULT_STYLE_FILE}'")
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
    args = parse_args(arg_list)

    if not os.path.exists(args.input_file):
        raise FileNotFoundError(f"File '{args.input_file}' does not exist.")
    elif not is_valid_extension(args.input_file):
        raise InvalidInputError("File must have one of the following extensions: osm, osm.pbf, osm.bz2.")
    elif args.style_file:
        if not os.path.exists(args.style_file):
            raise FileNotFoundError(f"File '{args.style_file}' does not exist.")
        elif not str(args.style_file).endswith(".lua"):
            raise InvalidInputError("File must have the '.lua' extension.")
    
    match args.flag:
        case 'd' | 'i' | 'ie':
            # Display content or (extended) information of OSM file
            run_osmium_cmd(args.flag, args.input_file)

        case 's' | 'r' | 'sr':
            # Sort, renumber OSM file or do both
            if not args.output_file:
                raise MissingInputError("An output file must be specified with '-o' flag.")
            run_osmium_cmd(args.flag, args.input_file, args.output_file)
    
        case "u":
            # Preprocess and upload OSM file to PostgreSQL database and then postprocess the data
            import_osm_to_db(args.input_file, args.force, args.pgpass, args.style_file, args.schema)

        case "b":
            # Extract bounding box based on relation ID and import to PostgreSQL
            if not args.relation_id:
                raise MissingInputError("Existing relation ID must be specified.")

            min_lon, min_lat, max_lon, max_lat = extract_bbox(args.relation_id)
            coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            run_osm2pgsql_cmd(CREDENTIALS, args.input_file, args.style_file, args.schema, args.force, args.pgpass, coords)
    
if __name__ == '__main__':
    main()
