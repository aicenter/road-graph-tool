import pathlib
import sys
import os
import subprocess
import logging

# CHANGE - file path to the config file
CONFIG_FILE = "config.ini"

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

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
    print(f"Usage: {os.path.basename(__file__)} -u [input_file] [style_file_path]")
    print("  Tag: ")
    print("   -u        : Upload OSM file to PostgreSQL database using osm2pgsql with the specified style file")
    print("               (Optional: specify style file path - default.lua is used otherwise)")


# Function to check if the file has a valid extension
def check_extension(file):
    valid_extensions = ["osm", "osm.pbf", "osm.bz2"]
    if not any(file.endswith(f".{ext}") for ext in valid_extensions):
        logger.error(f"File must have one of the following extensions: {', '.join(f'.{ext}' for ext in valid_extensions)}.")
        exit(1)

if __name__ == '__main__':
   # If no tag is used OR script is called with -h/--help
    if len(sys.argv) < 2 or (tag:=sys.argv[1]) in ["-h", "--help"]:
        display_help()
        exit(0)

    if len(sys.argv) < 3:
        logger.error("Insufficient arguments. Use \"process_osm.py -h/--help\" for hint.")
        exit(1)
    
    input_file = sys.argv[2]

    # Check if input file exists
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"File '{input_file}' does not exist.")

    check_extension(input_file)

    if tag == "-d":
        subprocess.run(["osmium", "show", input_file])
    elif tag == "-i":
        subprocess.run(["osmium", "fileinfo", input_file])
    elif tag == "-ie":
        subprocess.run(["osmium", "fileinfo", "-e", input_file])
    elif tag == "-r":
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            logger.error("An output file must be specified with '-o' tag.")
            exit(1)
        output_file = sys.argv[4]
        check_extension(output_file)
        subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
    elif tag == "-s":
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            logger.error("An output file must be specified with '-o' tag.")
            exit(1)
        output_file = sys.argv[4]
        check_extension(output_file)
        subprocess.run(["osmium", "sort", input_file, "-o", output_file])
    elif tag == "-u":
        style_file_path = sys.argv[3] if len(sys.argv) > 3 else "resources/lua_styles/default.lua"
        input_file = input_file

        parent_dir = pathlib.Path(__file__).parent.parent
        sys.path.append(str(parent_dir))
        from roadgraphtool.credentials_config import CREDENTIALS as config
        db_username = config.username
        db_host = config.db_host
        db_name = config.db_name
        db_server_port = config.db_server_port
        command = ["osm2pgsql", "-d", db_name, "-U", db_username, "-W", "-H", db_host, "-P", str(db_server_port),
            "--output=flex", "-S", style_file_path, input_file, "-x"]
        subprocess.run(command)
    else:
        logger.error(f"Invalid tag. Call {os.path.basename(__file__)} -h/--help to display help.")