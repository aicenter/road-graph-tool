import argparse
from pathlib import Path
import re
import os
import subprocess
import tempfile
from typing import Any
import requests
import logging

import roadgraphtool.exec

from roadgraphtool.exceptions import InvalidInputError, MissingInputError

RESOURCES_DIR = Path(__file__).parent.parent / "roadgraphtool/resources"

def setup_logger(logger_name: str) -> logging.Logger:
    log = logging.getLogger(logger_name)
    log.setLevel(logging.DEBUG)
    # setup formatting
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    log.addHandler(handler)
    # stop logger from emitting messages
    log.propagate = False
    return log

logger = setup_logger('filter_osm')

def is_valid_extension(file: Path) -> bool:
    """Return True if the file has a valid extension.
    
    Valid extensions: osm, osm.pbf, osm.bz2
    """
    valid_extensions = {".osm", ".osm.pbf", ".bz2"}
    return "".join(file.suffixes) in valid_extensions

def check_strategy(strategy: str | None):
    """Raise InvalidInputError if strategy type is not valid."""
    valid_strategies = ["simple", "complete_ways", "smart"]
    if strategy and strategy not in valid_strategies:
        raise InvalidInputError(f"Invalid strategy type. Call {os.path.basename(__file__)} -h/--help to display help.")
    logger.debug("Strategy validity checked.")

def load_multipolygon_by_id(relation_id: str) -> bytes | Any:
    """Return multipolygon content based on relation ID."""
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    response = requests.get(url)
    response.raise_for_status()
    logger.debug("Multipolygon content loaded.")
    return response.content

def extract_id(input_file: Path, output_file: Path, relation_id: str, strategy: str = None):
    """Filter out data based on relation ID."""
    logger.debug("Extracting multipolygon with relation ID %s...")
    content = load_multipolygon_by_id(relation_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".osm") as tmp_file:
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
        cmd = ["osmium", "extract", "-p", tmp_file_path, str(input_file), "-o", str(output_file)]
        if strategy:
            cmd.extend(["-s", strategy])
        res = roadgraphtool.exec.call_executable(cmd)
        if res:
            logger.debug("ID extraction completed.")
    
def extract_bbox(input_file: str, coords: str, strategy: str = None):
    """Extract data based on bounding box with osmium."""
    float_regex = r'[0-9]+(.[0-9]+)?' # should match four floats
    coords_regex = f'{float_regex},{float_regex},{float_regex},{float_regex}'
    if re.match(coords_regex, coords):
        logger.debug("Extracting bounding box with coords %s...", coords)
        cmd = ["osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"]
    elif os.path.isfile(coords) and coords.endswith((".json", ".geojson")):
        logger.debug("Extracting bounding box with coords in file %s...", coords)
        cmd = ["osmium", "extract", "-c", coords, input_file]
    else:
        raise InvalidInputError("Invalid coordinates or config file.")

    if strategy:
        cmd.extend(["-s", strategy])
    
    res = subprocess.run(cmd)
    if not res.returncode:
        logger.info("Bounding box extraction completed.")

def run_osmium_filter(input_file: str, expression_file: str, omit_referenced: bool):
    """Filter objects based on tags in expression file.

    Untagged nodes and members referenced in ways and relations respectively will not 
    be added to output if omit_referenced set to True.
    """
    cmd = ["osmium", "tags-filter", input_file, "-e", expression_file, "-o", "filtered.osm.pbf"]
    if omit_referenced:
        cmd.extend(["-R"])
    res = subprocess.run(cmd)
    if not res.returncode:
        logger.info("Tag filtering completed.")

def filter_highways(input_file: str, omit_referenced: bool):
    """Filter objects with highway tag. 
    
    Untagged nodes and members referenced in ways and relations respectively will not 
    be added to output if omit_referenced set to True.
    """
    content = "nwr/highway"
    cmd = ["osmium", "tags-filter", input_file, content, "-o", "filtered.osm.pbf"]
    if omit_referenced:
        cmd.extend(["-R"])
    res = subprocess.run(cmd)
    if not res.returncode:
        logger.info("Highway filtering completed.")

def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter OSM files with various operations.", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("flag", choices=["id", "b", "f", "h"], metavar="flag",
                        help="""
id : Filter geographic objects based on relation ID
b  : Filter geographic objects based on bounding box (with osmium)
f  : Filter objects based on tags in expression_file
h  : Filter objects based on highway tag
""")
    parser.add_argument('input_file', help='Path to input OSM file')
    parser.add_argument("-e", dest="expression_file", help="Path to expression file for filtering tags (required for 'f' flag)")
    parser.add_argument("-c", dest="coords", help="Bounding box coordinates or path to config file (required for 'b' flag)")
    parser.add_argument("-rid", dest="relation_id", help="Relation ID (required for 'id' flag)")
    parser.add_argument("-s", dest="strategy", help="Strategy type (optional for 'id', 'b' flags)")
    parser.add_argument("-R", dest="omit_referenced", action="store_true", help="Omit referenced objects (optional for 'f', 'h' flag)")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Enable verbose output (DEBUG level logging)")

    args = parser.parse_args(arg_list)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return args

def main(arg_list: list[str] | None = None):
    args = parse_args(arg_list)

    input_file_path = Path(args.input_file)

    if not input_file_path.exists():
        raise FileNotFoundError(f"File '{args.input_file}' does not exist.")
    elif not is_valid_extension(input_file_path):
        raise InvalidInputError("File must have one of the following extensions: osm, osm.pbf, osm.bz2")
    
    match args.flag:
        case "id":
            # Filter geographic objects based on relation ID
            if not args.relation_id:
                raise MissingInputError("Existing relation ID must be specified.")
            
            check_strategy(args.strategy)

            output_file_path = input_file_path.parent / "id_extract.osm"
            
            extract_id(input_file_path, output_file_path, args.relation_id, args.strategy)

        case "b":
            # Filter geographic objects based on bounding box (with osmium)
            if not args.coords:
                raise MissingInputError("Coordinates or config file need to be specified with the 'b' flag.")
            
            check_strategy(args.strategy)
            
            extract_bbox(args.input_file, args.coords, args.strategy)

        case "f":
            # Filter objects based on tags in expression_file
            if not args.expression_file:
                raise MissingInputError("Expression file needs to be specified.")
            elif not os.path.exists(args.expression_file):
                raise FileNotFoundError(f"File '{args.expression_file}' does not exist.")

            run_osmium_filter(args.input_file, args.expression_file, args.omit_referenced)

        case "h":
            # Filter objects based on highway tag
            filter_highways(args.input_file, args.omit_referenced)

if __name__ == '__main__':
    main()