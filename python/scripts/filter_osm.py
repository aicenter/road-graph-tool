import pathlib
import re
import sys
import os
import subprocess
import requests
from scripts.find_bbox import find_min_max
from scripts.process_osm import check_extension

class InvalidInputError(Exception):
    pass

class MissingInputError(Exception):
    pass

def display_help():
    """Function to display usage information"""
    print(f"Usage: {os.path.basename(__file__)} [tag] [input_file]")
    print("Tag:")
    print("  -h/--help              : Display this help message")
    print("  -id                    : Filter geographic objects based on relation ID")
    print("  -b                     : Get bounding box of geographic objects from given relation ID (forwared to process_osm)")
    print("  -bos                   : Filter geographic objects based on bounding box (with osmium)")
    print("  -t [expression_file]   : Filter objects based on tags in expression_file")
    print("Option:")
    print("  -s                     : Specify strategy type (optional for: -id, -b)")

def check_strategy(strategy):
    """Function to check strategy type"""
    valid_strategies = ["simple", "complete_ways", "smart"]
    return strategy in valid_strategies

def load_multigon_by_id(relation_id):
    """Function to load multigon content by relation id"""
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def extract_id(relation_id, input_file, strategy=None):
    """Function to filter out data based on input id"""
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    tmp_file = str(parent_dir) + "/resources/to_extract.osm"
    config_path = str(parent_dir) + "/resources/extract-id.geojson"

    content = load_multigon_by_id(relation_id)
    with open(tmp_file, 'wb') as f:
        f.write(content)
    
    command = ["osmium", "extract", "-c", config_path, input_file]
    if strategy:
        command.extend(["-s", strategy])
    
    subprocess.run(command)
    os.remove(tmp_file)

def extract_bbox_osm2pgsql(relation_id):
    """Function to extract based on bounding box with osm2pgsql"""
    content = load_multigon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    return min_lon, min_lat, max_lon, max_lat

def extract_bbox_osmium(coords, input_file, strategy=None):
    """Function to extract based on bounding box with osmium"""
    # should match four floats:
    coords_regex = '[0-9]+(.[0-9]+)?,[0-9]+(.[0-9]+)?,[0-9]+(.[0-9]+)?,[0-9]+(.[0-9]+)?'
    if re.match(coords_regex, coords):
        command = ["osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"]
    elif os.path.isfile(coords):
        command = ["osmium", "extract", "-c", coords, input_file]
    else:
        command = None

    if strategy:
        command.extend(["-s", strategy])
    
    if command:
        subprocess.run(command)
    else:
        raise InvalidInputError("Invalid coordinates or config file.")

if __name__ == '__main__':
    # If no tag is used OR script is called with -h/--help
    if len(sys.argv) < 2 or (tag:=sys.argv[1]) in ("-h", "--help"):
        display_help()
    elif tag == "-id":
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify relation ID and input file.")

        relation_id = sys.argv[2]
        input_file = sys.argv[3]
        check_extension(input_file)
        if len(sys.argv) == 5 and sys.argv[4] == '-s':
            raise MissingInputError("Missing specified strategy type.")
        strategy = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "-s" else None
        
        if strategy and not check_strategy(strategy):
            raise InvalidInputError("Invalid strategy type. Call script.py -h/--help to display help.")
        
        extract_id(relation_id, input_file, strategy)

    elif tag == "-b":
        if len(sys.argv) < 3:
            raise MissingInputError("You need to specify relation ID.")
        relation_id = sys.argv[2]
        input_file = sys.argv[3]
        check_extension(input_file)
        min_lon, min_lat, max_lon, max_lat = extract_bbox_osm2pgsql(relation_id, input_file)
        print(f"{min_lon}, {min_lat}, {max_lon}, {max_lat}")

    elif tag == "-bos":
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify either coordinates or config file with coordinates and input file.")
        coords = sys.argv[2]
        input_file = sys.argv[3]
        check_extension(input_file)
        strategy = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "-s" else None
        
        if strategy and not check_strategy(strategy):
            raise InvalidInputError("Invalid strategy type. Call script.py -h/--help to display help.")
        extract_bbox_osmium(coords, input_file, strategy)

    elif tag == "-t":
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify expression file and input file.")
        expression_file = sys.argv[2]
        input_file = sys.argv[3]
        check_extension(input_file)
        subprocess.run(["osmium", "tags-filter", input_file, "-e", expression_file, "-o", "filtered.osm.pbf"])

    else:
        raise InvalidInputError(f"Invalid tag. Call {os.path.basename(__file__)} -h/--help to display help.")