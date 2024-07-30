import pathlib
import re
import sys
import os
import subprocess
import requests
from find_bbox import find_min_max
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

def display_help():
    """Function to display usage information"""
    print(f"Usage: {os.path.basename(__file__)} [tag] [input_file]")
    print("Tag:")
    print("  -h/--help              : Display this help message")
    print("  -id                    : Filter geographic objects based on ID")
    print("  -b                     : Filter geographic objects based on bounding box (with osm2pgsql)")
    print("  -bos                   : Filter geographic objects based on bounding box (with osmium)")
    print("  -t [expression_file]   : Filter objects based on tags in expression_file")
    print("Option:")
    print("  -s                     : Specify strategy type (optional for: -id, -b)")

def check_strategy(strategy):
    """Function to check strategy type"""
    valid_strategies = ["simple", "complete_ways", "smart"]
    return strategy in valid_strategies

def extract_id(relation_id, input_file, strategy=None):
    """Function to filter out data based on input id"""
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    tmp_file = str(parent_dir) + "/resources/to-extract.osm"
    path = str(parent_dir) + "/resources/extract-id.geojson"
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(tmp_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    
    command = ["osmium", "extract", "-c", path, input_file]
    if strategy:
        command.extend(["-s", strategy])
    
    subprocess.run(command)
    os.remove(tmp_file)

def extract_bbox_osm2pgsql(relation_id):
    """Function to extract based on bounding box with osm2pgsql"""
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    response = requests.get(url)
    response.raise_for_status()
    min_lon, min_lat, max_lon, max_lat = find_min_max(response.content)
    return min_lon, min_lat, max_lon, max_lat

def extract_bbox_osmium(coords, input_file, strategy=None):
    """Function to extract based on bounding box with osmium"""
    # should match four floats:
    coords_regex = '^[0-9]+(\.[0-9]+)?,[0-9]+(\.[0-9]+)?,[0-9]+(\.[0-9]+)?,[0-9]+(\.[0-9]+)?$'
    command = ["osmium", "extract", "-b" if re.match(coords_regex, coords) else "-c", coords, input_file, "-o", "extracted-bbox.osm.pbf"]
    
    if strategy:
        command.extend(["-s", strategy])
    
    subprocess.run(command)

if __name__ == '__main__':
    # If no tag is used OR script is called with -h/--help
    if len(sys.argv) < 2 or (tag:=sys.argv[1]) in ("-h", "--help"):
        display_help()
        exit(0)

    if tag == "-id":
        if len(sys.argv) < 4:
            logger.error("You need to specify relation ID and input file.")
            exit(1)
        relation_id = sys.argv[2]
        input_file = sys.argv[3]
        if len(sys.argv) == 5 and sys.argv[4] == '-s':
            logger.error("Missing specified strategy type.")
            exit(1)
        strategy = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "-s" else None
        
        if strategy and not check_strategy(strategy):
            logger.error("Invalid strategy type. Call script.py -h/--help to display help.")
            exit(1)
        
        extract_id(relation_id, input_file, strategy)

    elif tag == "-b":
        if len(sys.argv) < 3:
            logger.error("You need to specify relation ID.")
            exit(1)
        relation_id = sys.argv[2]
        input_file = sys.argv[3]
        min_lon, min_lat, max_lon, max_lat = extract_bbox_osm2pgsql(relation_id, input_file)
        print(f"{min_lon}, {min_lat}, {max_lon}, {max_lat}")

    elif tag == "-bos":
        if len(sys.argv) < 4:
            logger.error("You need to specify either coordinates or config file with coordinates and input file.")
            exit(1)
        coords = sys.argv[2]
        input_file = sys.argv[3]
        strategy = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "-s" else None
        
        if strategy and not check_strategy(strategy):
            logger.error("Invalid strategy type. Call script.py -h/--help to display help.")
            exit(1)
        
        extract_bbox_osmium(coords, input_file, strategy)

    elif tag == "-t":
        if len(sys.argv) < 4:
            logger.error("You need to specify expression file and input file.")
            exit(1)
        expression_file = sys.argv[2]
        input_file = sys.argv[3]
        subprocess.run(["osmium", "tags-filter", input_file, "-e", expression_file, "-o", "filtered.osm.pbf"])

    else:
        logger.error(f"Invalid tag. Call {os.path.basename(__file__)} -h/--help to display help.")