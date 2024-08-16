import argparse
import re
import os
import subprocess
import tempfile
import requests

class InvalidInputError(Exception):
    pass

class MissingInputError(Exception):
    pass

def display_help():
    """Function to display help information instead of parser's default"""
    help_text = f"""Usage: {os.path.basename(__file__)} [tag] [input_file] [option]
 Tag:
    -h/--help         : Display this help message
    id                : Filter geographic objects based on relation ID
    b                 : Filter geographic objects based on bounding box (with osmium)
    t                 : Filter objects based on tags in expression_file
 Option:
    [relation_id]     : Specify relation_id (required for 'id' tag)
    [bbox]            : Specify bouding box (required for 'b' tag)
                        (Bounding box is specified directly or in config geojson file)
    [expression_file] : Specify path to expression file
    -s [strategy]     : Specify strategy type (optional for: 'id', 'b')"""
    print(help_text)

def is_valid_extension(file):
    """Function to check if the file has a valid extension."""
    valid_extensions = ["osm", "osm.pbf", "osm.bz2"]
    return any(file.endswith(f".{ext}") for ext in valid_extensions)

def check_strategy(strategy):
    """Function to check strategy type"""
    valid_strategies = ["simple", "complete_ways", "smart"]
    return strategy in valid_strategies

def load_multipolygon_by_id(relation_id):
    """Function to load multigon content by relation ID."""
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def extract_id(relation_id, input_file, strategy=None):
    """Function to filter out data based on relation ID."""
    content = load_multipolygon_by_id(relation_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".osm") as tmp_file:
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
        command = ["osmium", "extract", "-p", tmp_file_path, input_file, "-o", "resources/id_extract.osm"]
        if strategy:
            command.extend(["-s", strategy])
        subprocess.run(command)

def extract_bbox(coords, input_file, strategy=None):
    """Function to extract based on bounding box with osmium"""
    # should match four floats:
    float_regex = r'[0-9]+(.[0-9]+)?'
    coords_regex = f'{float_regex},{float_regex},{float_regex},{float_regex}'
    if re.match(coords_regex, coords):
        command = ["osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"]
    elif os.path.isfile(coords):
        command = ["osmium", "extract", "-c", coords, input_file]
    else:
        raise InvalidInputError("Invalid coordinates or config file.")

    if strategy:
        command.extend(["-s", strategy])
    
    subprocess.run(command)

def run_osmium_filter(input_file, expression_file):
    """Function to filter objects based on tags in expression file."""
    subprocess.run(["osmium", "tags-filter", input_file, "-e", expression_file, "-o", "filtered.osm.pbf"])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Filter OSM files with various operations.", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("tag", choices=["id", "b", "t"])
    parser.add_argument('input_file', nargs='?', help='Path to input OSM file')
    parser.add_argument("relation_id", nargs="?", help="relation ID (required for 'b' tag)")
    parser.add_argument("expression_file", nargs="?", help="Path to expression file for filtering tags (required for 't' tag)")
    parser.add_argument("coords",nargs="?",help="Bounding box coordinates or path to config file (required for 'b' tag)")
    parser.add_argument("-s", dest="strategy", help="Strategy type (optional for 'id', 'b' tags)")

    parser.format_help = lambda: display_help()
    args = parser.parse_args()

    if not args.input_file:
        raise InvalidInputError(f"Input file not provided.")
    elif not os.path.exists(args.input_file):
        raise FileNotFoundError(f"File '{args.input_file}' does not exist.")
    elif not is_valid_extension(args.input_file):
        raise InvalidInputError(f"File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    
    if args.tag == "id":
        # Filter geographic objects based on relation ID
        if not args.relation_id:
            raise MissingInputError("You need to specify relation ID.")
        
        if args.strategy and not check_strategy(args.strategy):
            raise InvalidInputError(f"Invalid strategy type. Call {os.path.basename(__file__)}  -h/--help to display help.")
        
        extract_id(args.relation_id, args.input_file, args.strategy)

    elif args.tag == "b":
        # Filter geographic objects based on bounding box (with osmium)
        if not args.coords:
            raise MissingInputError("You need to specify coordinates or a config file with the 'b' tag.")
        
        if args.strategy and not check_strategy(args.strategy):
            raise InvalidInputError(f"Invalid strategy type. Call {os.path.basename(__file__)} -h/--help to display help.")
        extract_bbox(args.coords, args.input_file, args.strategy)

    elif args.tag == "t":
        # Filter objects based on tags in expression_file
        if not args.expression_file:
            raise MissingInputError("You need to specify expression file.")

        run_osmium_filter(args.input_file, args.expression_file)
