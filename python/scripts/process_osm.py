import sys
import os
import subprocess
from roadgraphtool.credentials_config import CREDENTIALS as config

# File path to the config file
CONFIG_FILE = "config.ini"

# Function to display usage information
def display_help():
    print("Usage: $0 [tag] [input_file]")
    print("  Tag: ")
    print("   -h/--help : Display this help message")
    print("   -d        : Display OSM file")
    print("   -i        : Display information about OSM file")
    print("   -ie       : Display extended information about OSM file")
    print("Usage: $0 [tag] [input_file] -o [output_file]")
    print("  Tag: ")
    print("   -r        : Renumber object IDs in OSM file (Requires specifying output file with '-o' tag)")
    print("   -s        : Sort OSM file based on IDs (Requires specifying output file with '-o' tag)")
    print("Usage: $0 -l [input_file] [style_file_path]")
    print("  Tag: ")
    print("   -l        : Import OSM file to PostgreSQL database using osm2pgsql with the specified style file")
    print("               (Optional: specify style file path - default.lua is used otherwise)")


# Function to check if the file has a valid extension
def check_extension(file):
    valid_extensions = ["osm", "osm.pbf", "osm.bz2"]
    if not any(file.endswith(f".{ext}") for ext in valid_extensions):
        # TODO: logging
        print(f"Error: File must have one of the following extensions: {', '.join(f'.{ext}' for ext in valid_extensions)}.")
        exit(1)


if __name__ == '__main__':
   # If no tag is used OR script is called with -h/--help
    if len(sys.argv) < 2 and (tag:=sys.argv[1]) in ["-h", "--help"]:
        display_help()
        exit(0)

    input_file = sys.argv[2]

    # Check if input file exists
    if not os.path.exists(input_file):
        # TODO: logging
        print(f"Error: File '{input_file}' does not exist.")
        exit(1)

    check_extension(input_file)

    if tag == "-d":
        subprocess.run(["osmium", "show", input_file])
    elif tag == "-i":
        subprocess.run(["osmium", "fileinfo", "-e", input_file])
    elif tag == "-r":
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            # TODO: logging
            print("Error: An output file must be specified with '-o' tag.")
            exit(1)
        output_file = sys.argv[4]
        check_extension(output_file)
        subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
    elif tag == "-s":
        if len(sys.argv) < 5 or sys.argv[3] != "-o":
            # TODO: logging
            print("Error: An output file must be specified with '-o' tag.")
            exit(1)
        output_file = sys.argv[4]
        check_extension(output_file)
        subprocess.run(["osmium", "sort", input_file, "-o", output_file])
    elif tag == "-l":
        style_file_path = sys.argv[3] if len(sys.argv) > 3 else "resources/lua_styles/default.lua"
        input_file = input_file
        db_username = config.username
        db_host = config.db_host
        db_name = config.db_name
        db_server_port = config.db_server_port
        subprocess.run([
            "osm2pgsql", "-d", db_name, "-U", db_username, "-W", "-H", db_host, "-P", db_server_port,
            "--output=flex", "-S", style_file_path, input_file, "-x"
        ])
    else:
        # TODO: logging
        print("Invalid tag. Use \"script.py -h/--help\" for hint.")
        exit(1)