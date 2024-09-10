import argparse
import os
import subprocess
import logging

from roadgraphtool.credentials_config import CREDENTIALS as config, CredentialsConfig
from scripts.filter_osm import InvalidInputError, MissingInputError, load_multipolygon_by_id, is_valid_extension, setup_logger
from scripts.find_bbox import find_min_max

DEFAULT_STYLE_FILE = "resources/lua_styles/default.lua"

logger = setup_logger()

def extract_bbox(relation_id: int) -> tuple[float, float, float, float]:
    """Return tuple of floats based on bounding box coordinations."""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    logger.debug(f"Bounding box found: {min_lon},{min_lat},{max_lon},{max_lat}.")
    return min_lon, min_lat, max_lon, max_lat

def run_osmium_cmd(tag: str, input_file: str, output_file: str = None):
    """Run osmium command based on tag."""
    if output_file and not is_valid_extension(output_file):
        raise InvalidInputError("File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    match tag:
        case "d":
            subprocess.run(["osmium", "show", input_file])
        case "i":
            subprocess.run(["osmium", "fileinfo", input_file])
        case "ie":
            subprocess.run(["osmium", "fileinfo", "-e", input_file])
        case 'r':
            subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
            logger.info("Renumbering of OSM data completed.")
        case 's':
            subprocess.run(["osmium", "sort", input_file, "-o", output_file])
            logger.info("Sorting of OSM data completed.")
        case 'sr':
            tmp_file = 'tmp.osm'
            subprocess.run(["osmium", "sort", input_file, "-o", tmp_file])
            logger.info("Sorting of OSM data completed.")
            subprocess.run(["osmium", "renumber", tmp_file, "-o", output_file])
            os.remove(tmp_file)
            logger.info("Renumbering of OSM data completed.")

def run_osm2pgsql_cmd(config: CredentialsConfig, input_file: str, style_file_path: str, coords: str| list[int] = None):
    """Import data from input_file using osm2pgsql."""
    logger.debug("Setting up command...")
    command = ["osm2pgsql", "-d", config.db_name, "-U", config.username, "-W", "-H", config.db_host, 
               "-P", str(config.db_server_port), "--output=flex", "-S", style_file_path, input_file, "-x"]
    if coords:
        command.extend(["-b", coords])
    print(logger.level)
    if logger.level == logging.DEBUG:
        command.extend(['--log-level=debug'])

    logger.info(f"Begin importing with command: '{' '.join(command)}'")
    subprocess.run(command)

def import_osm_to_db(style_file_path: str = None) -> int:
    """Return the size of OSM file in bytes if file found and imports OSM file do database specified in config.ini file.

    The **default.lua** style file is used if not specified or set otherwise.
    The function expects the OSM file to be saved as **resources/to_import.***.
    """
    input_files = ["resources/to_import.osm", "resources/to_import.osm.pbf", "resources/to_import.osm.bz2"]
    input_file = None
    for file in input_files:
        if os.path.exists(file) and is_valid_extension(file):
            input_file = file
            file_size = os.path.getsize(input_file)
            break
    if not input_file:
        raise FileNotFoundError("There is no valid file to import.")
    if style_file_path is None:
        style_file_path = DEFAULT_STYLE_FILE
    if not os.path.exists(style_file_path):
        raise FileNotFoundError(f"Style file {style_file_path} does not exist.")
    run_osm2pgsql_cmd(config, input_file, style_file_path)
    logger.debug("Importing completed.")
    return file_size

def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process OSM files and interact with PostgreSQL database.", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("tag", choices=["d", "i", "ie", "s", "r", "sr", "b", "u"], metavar="tag",
                        help="""
d  : Display OSM file
i  : Display information about OSM file
ie : Display extended information about OSM file
s  : Sort OSM file based on IDs
r  : Renumber object IDs in OSM file
sr : Sort and renumber objects in OSM file
u  : Upload OSM file to PostgreSQL database using osm2pgsql
b  : Extract greatest bounding box from given relation ID of 
     input_file and upload to PostgreSQL database using osm2pgsql"""
)
    parser.add_argument('input_file', help="Path to input OSM file")
    parser.add_argument("-id", dest="relation_id", help="Relation ID (required for 'b' tag)")
    parser.add_argument("-l", dest="style_file", nargs='?', default="resources/lua_styles/default.lua", help="Path to style file (optional for 'b', 'u' tag)")
    parser.add_argument("-o", dest="output_file", help="Path to output file (required for 's', 'r', 'sr' tag)")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Enable verbose output (DEBUG level logging)")

    args = parser.parse_args(arg_list)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

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
        elif not args.style_file.endswith(".lua"):
            raise InvalidInputError("File must have the '.lua' extension.")
    
    match args.tag:
        case 'd' | 'i' | 'ie':
            # Display content or (extended) information of OSM file
            run_osmium_cmd(args.tag, args.input_file)

        case 's' | 'r' | 'sr':
            # Sort, renumber OSM file or do both
            if not args.output_file:
                raise MissingInputError("An output file must be specified with '-o' tag.")
            run_osmium_cmd(args.tag, args.input_file, args.output_file)
    
        case "u":
            # Upload OSM file to PostgreSQL database
            run_osm2pgsql_cmd(config, args.input_file, args.style_file)
        case "b":
            # Extract bounding box based on relation ID and import to PostgreSQL
            if not args.relation_id:
                raise MissingInputError("Existing relation ID must be specified.")

            min_lon, min_lat, max_lon, max_lat = extract_bbox(args.relation_id)
            coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            run_osm2pgsql_cmd(config, args.input_file, args.style_file, coords)
    
if __name__ == '__main__':
    main()