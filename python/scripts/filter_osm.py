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

def is_valid_extension(file: str):
    """Function to check if the file has a valid extension."""
    valid_extensions = ["osm", "osm.pbf", "osm.bz2"]
    return any(file.endswith(f".{ext}") for ext in valid_extensions)

def check_strategy(strategy: str | None):
    """Function to check strategy type"""
    valid_strategies = ["simple", "complete_ways", "smart"]
    if strategy and strategy not in valid_strategies:
        raise InvalidInputError(f"Invalid strategy type. Call {os.path.basename(__file__)} -h/--help to display help.")

def load_multipolygon_by_id(relation_id: str):
    """Function to load multigon content by relation ID."""
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def extract_id(input_file: str, relation_id: str, strategy: str = None):
    """Function to filter out data based on relation ID."""
    content = load_multipolygon_by_id(relation_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".osm") as tmp_file:
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
        command = ["osmium", "extract", "-p", tmp_file_path, input_file, "-o", "resources/id_extract.osm"]
        if strategy:
            command.extend(["-s", strategy])
        subprocess.run(command)

def extract_bbox(input_file: str, coords: str, strategy: str = None):
    """Function to extract based on bounding box with osmium"""
    # should match four floats:
    float_regex = r'[0-9]+(.[0-9]+)?'
    coords_regex = f'{float_regex},{float_regex},{float_regex},{float_regex}'
    if re.match(coords_regex, coords):
        command = ["osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"]
    elif os.path.isfile(coords) and coords.endswith((".json", ".geojson")):
        command = ["osmium", "extract", "-c", coords, input_file]
    else:
        raise InvalidInputError("Invalid coordinates or config file.")

    if strategy:
        command.extend(["-s", strategy])
    
    subprocess.run(command)

def run_osmium_filter(input_file: str, expression_file: str, omit_referenced: bool):
    """Function to filter objects based on tags in expression file.
    Nodes referenced in ways and members referenced in relations will not 
    be added to output if omit_referenced set to True.
    """
    cmd = ["osmium", "tags-filter", input_file, "-e", expression_file, "-o", "filtered.osm.pbf"]
    if omit_referenced:
        cmd.extend(["-R"])
    subprocess.run(cmd)

def parse_args(arg_list: list[str] | None):
    parser = argparse.ArgumentParser(description="Filter OSM files with various operations.", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("tag", choices=["id", "b", "f"], metavar="tag",
                        help="""
id : Filter geographic objects based on relation ID
b  : Filter geographic objects based on bounding box (with osmium)
f  : Filter objects based on tags in expression_file
""")
    parser.add_argument('input_file', nargs='?', help='Path to input OSM file')
    parser.add_argument("-e", dest="expression_file", nargs="?", help="Path to expression file for filtering tags (required for 'f' tag)")
    parser.add_argument("-c", dest="coords", nargs="?",help="Bounding box coordinates or path to config file (required for 'b' tag)")
    parser.add_argument("-rid", dest="relation_id", nargs="?", help="relation ID (required for 'b' tag)")
    parser.add_argument("-s", dest="strategy", help="Strategy type (optional for 'id', 'b' tags)")
    parser.add_argument("-R", dest="omit_referenced", action="store_true", help="Omit referenced objects (optional for 'f' tag)")

    args = parser.parse_args(arg_list)

    return args

def main(arg_list: list[str] | None = None):
    args = parse_args(arg_list)

    if not os.path.exists(args.input_file):
        raise FileNotFoundError(f"File '{args.input_file}' does not exist.")
    elif not is_valid_extension(args.input_file):
        raise InvalidInputError("File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    
    match args.tag:
        case "id":
            # Filter geographic objects based on relation ID
            if not args.relation_id:
                raise MissingInputError("Existing relation ID must be specified.")
            
            check_strategy(args.strategy)
            
            extract_id(args.input_file, args.relation_id, args.strategy)

        case "b":
            # Filter geographic objects based on bounding box (with osmium)
            if not args.coords:
                raise MissingInputError("Coordinates or config file need to be specified with the 'b' tag.")
            
            check_strategy(args.strategy)
            
            extract_bbox(args.input_file, args.coords, args.strategy)

        case "f":
            # Filter objects based on tags in expression_file
            if not args.expression_file:
                raise MissingInputError("Expression file needs to be specified.")
            elif not os.path.exists(args.expression_file):
                raise FileNotFoundError(f"File '{args.expression_file}' does not exist.")

            run_osmium_filter(args.input_file, args.expression_file, args.omit_referenced)

if __name__ == '__main__':
    main()