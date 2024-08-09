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
    print(f"Usage: {os.path.basename(__file__)} [tag] [input_file]")
    print("  Tag: ")
    print("   -h/--help : Display this help message")
    print("   -d        : Display OSM file")
    print("   -i        : Display information about OSM file")
    print("   -ie       : Display extended information about OSM file")
    print(f"Usage: {os.path.basename(__file__)}[tag] [input_file] -o [output_file]")
    print("  Tag: ")
    print("   -r        : Renumber object IDs in OSM file (Requires specifying output file with '-o' tag)")
    print("   -s        : Sort OSM file based on IDs (Requires specifying output file with '-o' tag)")
    print(f"Usage: {os.path.basename(__file__)} -u [input_file] [style_file]")
    print("  Tag: ")
    print("   -u        : Upload OSM file to PostgreSQL database using osm2pgsql with the specified style file")
    print("               (Optional: specify style file - default.lua is used otherwise)")
    print(f"Usage: {os.path.basename(__file__)} -b [input_file] [relation_id] [style_file]")
    print("   -b        : Extract greatest bounding box from given relation ID of input_file and upload to PostgreSQL database using osm2pgsql.")
    print("               (Optional: specify style file - default.lua is used otherwise)")

def extract_bbox(relation_id):
    """Function to determine bounding box"""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    return min_lon, min_lat, max_lon, max_lat

if __name__ == '__main__':
   # If no tag is used OR script is called with -h/--help
    if len(sys.argv) < 2 or (tag:=sys.argv[1]) in ["-h", "--help"]:
        display_help()

    elif len(sys.argv) < 3:
        raise MissingInputError(f"Insufficient arguments. Use \"{os.path.basename(__file__)} -h/--help\" for hint.")
    elif not os.path.exists((input_file:=sys.argv[2])):
        raise FileNotFoundError(f"File '{input_file}' does not exist.")
    elif not is_valid_extension(input_file):
        raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    
    elif tag == "-d":
        subprocess.run(["osmium", "show", input_file])
    elif tag == "-i":
        subprocess.run(["osmium", "fileinfo", input_file])
    elif tag == "-ie":
        subprocess.run(["osmium", "fileinfo", "-e", input_file])
    elif tag == "-r":
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            raise MissingInputError("An output file must be specified with '-o' tag.")
        output_file = sys.argv[4]
        if not is_valid_extension(output_file):
            raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
        subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
    elif tag == "-s":
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            raise MissingInputError("An output file must be specified with '-o' tag.")
        output_file = sys.argv[4]
        if not is_valid_extension(output_file):
            raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
        subprocess.run(["osmium", "sort", input_file, "-o", output_file])
    elif tag == "-b":
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify input file and relation ID.")
        relation_id = sys.argv[3]
        min_lon, min_lat, max_lon, max_lat = extract_bbox(relation_id)
        coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        # print(coords)
        style_file_path = sys.argv[4] if len(sys.argv) > 4 else "resources/lua_styles/default.lua"
        input_file = input_file
        db_username = config.username
        db_host = config.db_host
        db_name = config.db_name
        db_server_port = config.db_server_port
        command = ["osm2pgsql", "-d", db_name, "-U", db_username, "-W", "-H", db_host, "-P", str(db_server_port),
            "-b", coords, "--output=flex", "-S", style_file_path, input_file, "-x"]
        # subprocess.run(command)

    elif tag == "-u":
        style_file_path = sys.argv[3] if len(sys.argv) > 3 else "resources/lua_styles/default.lua"
        input_file = input_file
        db_username = config.username
        db_host = config.db_host
        db_name = config.db_name
        db_server_port = config.db_server_port
        command = ["osm2pgsql", "-d", db_name, "-U", db_username, "-W", "-H", db_host, "-P", str(db_server_port),
            "--output=flex", "-S", style_file_path, input_file, "-x"]
        subprocess.run(command)
    else:
        raise InvalidInputError(f"Invalid tag. Call {os.path.basename(__file__)} -h/--help to display help.")