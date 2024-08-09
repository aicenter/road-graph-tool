import pathlib
import re
import sys
import os
import subprocess
import requests

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
    print("  -b                     : Filter geographic objects based on bounding box (with osmium)")
    print("  -t [expression_file]   : Filter objects based on tags in expression_file")
    print("Option:")
    print("  -s                     : Specify strategy type (optional for: -id, -b)")

# Function to check if the file has a valid extension
def is_valid_extension(file):
    valid_extensions = ["osm", "osm.pbf", "osm.bz2"]
    return any(file.endswith(f".{ext}") for ext in valid_extensions)

def check_strategy(strategy):
    """Function to check strategy type"""
    valid_strategies = ["simple", "complete_ways", "smart"]
    return strategy in valid_strategies

def load_multipolygon_by_id(relation_id):
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

    content = load_multipolygon_by_id(relation_id)
    with open(tmp_file, 'wb') as f:
        f.write(content)
    
    command = ["osmium", "extract", "-c", config_path, input_file]
    if strategy:
        command.extend(["-s", strategy])
    
    subprocess.run(command)
    os.remove(tmp_file)

def extract_bbox(coords, input_file, strategy=None):
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
        if not is_valid_extension(input_file):
            raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
        if len(sys.argv) == 5 and sys.argv[4] == '-s':
            raise MissingInputError("Missing specified strategy type.")
        strategy = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "-s" else None
        
        if strategy and not check_strategy(strategy):
            raise InvalidInputError("Invalid strategy type. Call script.py -h/--help to display help.")
        
        extract_id(relation_id, input_file, strategy)

    elif tag == "-b":
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify either coordinates or config file with coordinates and input file.")
        coords = sys.argv[2]
        input_file = sys.argv[3]
        if not is_valid_extension(input_file):
            raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
        strategy = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "-s" else None
        
        if strategy and not check_strategy(strategy):
            raise InvalidInputError("Invalid strategy type. Call script.py -h/--help to display help.")
        extract_bbox(coords, input_file, strategy)

    elif tag == "-t":
        if len(sys.argv) < 4:
            raise MissingInputError("You need to specify expression file and input file.")
        expression_file = sys.argv[2]
        input_file = sys.argv[3]
        if not is_valid_extension(input_file):
            raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
        subprocess.run(["osmium", "tags-filter", input_file, "-e", expression_file, "-o", "filtered.osm.pbf"])

    else:
        raise InvalidInputError(f"Invalid tag. Call {os.path.basename(__file__)} -h/--help to display help.")