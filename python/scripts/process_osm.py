import sys
import os
import subprocess

from roadgraphtool.credentials_config import CREDENTIALS as config
from scripts.filter_osm import InvalidInputError, MissingInputError, load_multipolygon_by_id, is_valid_extension
from scripts.find_bbox import find_min_max

class InvalidInputError(Exception):
    pass

class MissingInputError(Exception):
    pass

# Function to display usage information
def display_help():
    help_text = f"""Usage: {os.path.basename(__file__)} [tag] [input_file]
 Tag:
    -h/--help : Display this help message
    -d        : Display OSM file
    -i        : Display information about OSM file
    -ie       : Display extended information about OSM file
Usage: {os.path.basename(__file__)} [tag] [input_file] -o [output_file]
 Tag:
    -s        : Sort OSM file based on IDs (Requires specifying output file with '-o' tag)
    -r        : Renumber object IDs in OSM file (Requires specifying output file with '-o' tag)
    -sr       : Sort and renumber objects in OSM file (Requires specifying output file with '-o' tag)
Usage: {os.path.basename(__file__)} -u [input_file] [style_file]
 Tag:
    -u        : Upload OSM file to PostgreSQL database using osm2pgsql.
            (Optional: specify style file - default.lua is used otherwise)
Usage: {os.path.basename(__file__)} -b [input_file] [relation_id] [style_file]
    -b        : Extract greatest bounding box from given relation ID of input_file and upload to PostgreSQL database using osm2pgsql.
            (Optional: specify style file - default.lua is used otherwise)"""
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
    if  tag == "-d":
        subprocess.run(["osmium", "show", input_file])
    elif tag == "-i":
        subprocess.run(["osmium", "fileinfo", input_file])
    elif tag == "-ie":
        subprocess.run(["osmium", "fileinfo", "-e", input_file])
    elif tag == '-r':
        subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
    elif tag == '-s':
        subprocess.run(["osmium", "sort", input_file, "-o", output_file])
    elif tag == '-sr':
        tmp_file = 'tmp.osm'
        subprocess.run(["osmium", "sort", input_file, "-o", tmp_file])
        subprocess.run(["osmium", "renumber", tmp_file, "-o", output_file])
        os.remove(tmp_file)
    else:
        raise InvalidInputError(f"Invalid tag: {tag}. Call {os.path.basename(__file__)} -h/--help to display help.")

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
    if len(sys.argv) < 2 or (tag:=sys.argv[1]) in ["-h", "--help"]:
        # If no tag is used OR script is called with -h/--help
        display_help()

    elif len(sys.argv) < 3:
        raise MissingInputError(f"Insufficient arguments. Use \"{os.path.basename(__file__)} -h/--help\" for hint.")
    elif not os.path.exists((input_file:=sys.argv[2])):
        raise FileNotFoundError(f"File '{input_file}' does not exist.")
    elif not is_valid_extension(input_file):
        raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    elif tag == "-d":
        # Display content of OSM file
        run_osmium_command(tag, input_file)
    elif tag == "-i":
        # Display information about OSM file
        run_osmium_command(tag, input_file)
    elif tag == "-ie":
        # Display extended information about OSM file
        run_osmium_command(tag, input_file)
    elif tag == "-s":
        # Sort OSM file
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            raise MissingInputError("An output file must be specified with '-o' tag.")
        run_osmium_command(tag, input_file, sys.argv[4])
    elif tag == "-r":
        # Renumber OSM file
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            raise MissingInputError("An output file must be specified with '-o' tag.")
        run_osmium_command(tag, input_file, sys.argv[4])
    elif tag == "-sr":
        # Sort and renumber OSM file
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            raise MissingInputError("An output file must be specified with '-o' tag.")
        run_osmium_command(tag, input_file, sys.argv[4])
    elif tag == "-b":
        # Extract bounding box based on relation ID and import to PostgreSQL
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify input file and relation ID.")
        relation_id = sys.argv[3]
        min_lon, min_lat, max_lon, max_lat = extract_bbox(relation_id)
        coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"

        style_file_path = sys.argv[4] if len(sys.argv) > 4 else "resources/lua_styles/default.lua"
        run_osm2pgsql_command(config, style_file_path, input_file, coords)
    elif tag == "-u":
        # Upload OSM file to PostgreSQL database
        style_file_path = sys.argv[3] if len(sys.argv) > 3 else "resources/lua_styles/default.lua"
        run_osm2pgsql_command(config, style_file_path, input_file)
    else:
        raise InvalidInputError(f"Invalid tag. Call {os.path.basename(__file__)} -h/--help to display help.")