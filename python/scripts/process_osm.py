import argparse
import os
import subprocess

from roadgraphtool.credentials_config import CREDENTIALS as config
from scripts.filter_osm import InvalidInputError, MissingInputError, load_multipolygon_by_id, is_valid_extension
from scripts.find_bbox import find_min_max

def display_help():
    """Function to display help information instead of parser's default"""
    help_text = f"""Usage: {os.path.basename(__file__)} [tag] [input_file] [option]
Tag:
    -h/--help        : Display this help message
    d                : Display OSM file
    i                : Display information about OSM file
    ie               : Display extended information about OSM file
    s                : Sort OSM file based on IDs
    r                : Renumber object IDs in OSM file
    sr               : Sort and renumber objects in OSM file
    u                : Upload OSM file to PostgreSQL database using osm2pgsql.
    b                : Extract greatest bounding box from given relation ID of input_file 
                       and upload to PostgreSQL database using osm2pgsql
Option:
    [relation_id]    : Specify relation_id (required for 'b' tag)
    -l [style_file]  : Specify style_file (optional for: 'u', 'b' tag) - default.lua is used otherwise
    -o [output_file] : Specify output_file (required for 's', 'r', 'sr' tags)"""
    print(help_text)

def extract_bbox(relation_id):
    """Function to determine bounding box coordinations."""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    return min_lon, min_lat, max_lon, max_lat

def run_osmium_command(tag, input_file, output_file=None):
    """Function to run osmium command based on tag."""
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
        case 's':
            subprocess.run(["osmium", "sort", input_file, "-o", output_file])
        case 'sr':
            tmp_file = 'tmp.osm'
            subprocess.run(["osmium", "sort", input_file, "-o", tmp_file])
            subprocess.run(["osmium", "renumber", tmp_file, "-o", output_file])
            os.remove(tmp_file)

def run_osm2pgsql_command(config, style_file_path, input_file, coords=None):
    """Function to run osm2pgsql command."""
    command = ["osm2pgsql", "-d", config.db_name, "-U", config.username, "-W", "-H", config.db_host, 
               "-P", str(config.db_server_port), "--output=flex", "-S", style_file_path, input_file, "-x"]
    if coords:
        command.extend(["-b", coords])
    subprocess.run(command)

def import_osm_to_db():
    """Function to import OSM file do database specified in config.ini file.
    The function expects the OSM file to be saved as resources/to_import.*.
    The default.lua style file is used.
    """
    input_files = ["resources/to_import.osm", "resources/to_import.osm.pbf", "resources/to_import.osm.bz2"]
    input_file = None
    for file in input_files:
        if os.path.exists(file) and is_valid_extension(file):
            input_file = file
    if not input_file:
        raise FileNotFoundError("There is no file to import.")
    style_file_path = "resources/lua_styles/default.lua"
    run_osm2pgsql_command(config, style_file_path, input_file)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process OSM files and interact with PostgreSQL database.")

    parser.add_argument("tag", choices=["d", "i", "ie", "s", "r", "sr", "b", "u"])
    parser.add_argument('input_file', nargs='?', help='Path to input OSM file')
    parser.add_argument("relation_id", nargs="?", help="Relation ID (required for 'b' tag)")
    parser.add_argument("-l", dest="style_file", default='resources/lua_styles/default.lua', help="Path to style file (optional for 'b', 'u' tag)")
    parser.add_argument("-o", dest="output_file", help="Path to output file (required for 's', 'r', 'sr' tag)")

    parser.format_help = lambda: display_help()
    args = parser.parse_args()

    if not args.input_file:
        raise InvalidInputError(f"Input file not provided.")
    elif not os.path.exists(args.input_file):
        raise FileNotFoundError(f"File '{args.input_file}' does not exist.")
    elif not is_valid_extension(args.input_file):
        raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    
    if args.tag in ['d', 'i', 'ie']:
        # Display content or (extended) information of OSM file
        run_osmium_command(args.tag, args.input_file)

    elif args.tag in ['s', 'r', 'sr']:
        # Sort, renumber OSM file or do both
        if not args.output_file:
            raise MissingInputError("An output file must be specified with '-o' tag.")
        run_osmium_command(args.tag, args.input_file, args.output_file)
    
    elif args.tag == "u":
        # Upload OSM file to PostgreSQL database
        run_osm2pgsql_command(config, args.style_file, args.input_file)

    elif args.tag == "b":
        # Extract bounding box based on relation ID and import to PostgreSQL
        if not args.relation_id:
            raise MissingInputError("You need to specify relation ID.")

        min_lon, min_lat, max_lon, max_lat = extract_bbox(args.relation_id)
        coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"

        run_osm2pgsql_command(config, args.style_file, args.input_file, coords)
    