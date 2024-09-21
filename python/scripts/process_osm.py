import argparse
import os
import subprocess
from pathlib import Path

import roadgraphtool.log
from roadgraphtool.credentials_config import CREDENTIALS as config
from roadgraphtool.credentials_config import CredentialsConfig
from roadgraphtool.db import db
from scripts.filter_osm import (InvalidInputError, MissingInputError,
                                is_valid_extension, load_multipolygon_by_id)
from scripts.find_bbox import find_min_max
from scripts.install_sql import SQL_DIR, execute_sql_file, logging

RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"
STYLES_DIR = RESOURCES_DIR / "lua_styles"


def extract_bbox(relation_id: int):
    """Function to determine bounding box coordinations."""
    content = load_multipolygon_by_id(relation_id)
    min_lon, min_lat, max_lon, max_lat = find_min_max(content)
    return min_lon, min_lat, max_lon, max_lat


def run_osmium_cmd(tag: str, input_file: str, output_file: str):
    """Function to run osmium command based on tag."""
    if output_file and not is_valid_extension(output_file):
        raise InvalidInputError(
            "File must have one of the following extensions: osm, osm.pbf, osm.bz2"
        )
    match tag:
        case "d":
            subprocess.run(["osmium", "show", input_file])
        case "i":
            subprocess.run(["osmium", "fileinfo", input_file])
        case "ie":
            subprocess.run(["osmium", "fileinfo", "-e", input_file])
        case "r":
            subprocess.run(["osmium", "renumber", input_file, "-o", output_file])
        case "s":
            subprocess.run(["osmium", "sort", input_file, "-o", output_file])
        case "sr":
            tmp_file = "tmp.osm"
            subprocess.run(["osmium", "sort", input_file, "-o", tmp_file])
            subprocess.run(["osmium", "renumber", tmp_file, "-o", output_file])
            os.remove(tmp_file)


def run_osm2pgsql_cmd(
    config: CredentialsConfig,
    input_file: str,
    style_file_path: str,
    coords: str | list[int] | None = None,
    schema: str | None = None,
) -> int:
    """Function to run osm2pgsl command.
    Returns return code of the subprocess."""
    command = [
        "osm2pgsql",
        "-d",
        config.db_name,
        "-U",
        config.username,
        "-W",
        "-H",
        config.db_host,
        "-P",
        str(config.db_server_port),
        "--output=flex",
        "-S",
        style_file_path,
        input_file,
        "-x",
    ]
    if coords:
        command.extend(["-b", coords])
    if schema:
        command.extend(["--schema", schema])
    return subprocess.run(command).returncode


def post_process_osm_import(style_filename: str, schema: str | None = None) -> int:
    post_proc_dict = {"pipeline.lua": "after_import.sql"}

    if not post_proc_dict[style_filename]:
        logging.warning(f"No post-processing defined for style {style_filename}")
        return 0

    sql_filepath = SQL_DIR / post_proc_dict[style_filename]

    logging.info("Post-processing OSM import...")
    # retcode = db.execute_script(sql_filepath)
    command = [
        "psql",
        "-d",
        config.db_name,
        "-U",
        config.username,
        "-h",
        config.host,
        "-p",
        str(config.db_server_port),
    ]
    if schema:
        print(f"\n\nSEARCHPATH = {schema}")
        command.extend(["-c", f"SET search_path TO {schema};"])
    command.extend(
        [
            "-f",
            sql_filepath,
        ]
    )
    retcode = subprocess.run(command).returncode

    if retcode != 0:
        logging.error(f"Error during post-processing. Return code: {retcode}")
        return retcode
    logging.info("Post-processing done.")

    return 0


def import_osm_to_db(
    filename: str | None = None,
    style_filename: str = "pipeline.lua",
    schema: str | None = None,
) -> int:
    """Function to import OSM file specified in config.ini file to database.
    The function expects the OSM file to be saved as resources/to_import.*.
    The pipeline.lua style file is used as default style.

    The function will try to import the file with the following extensions:
        .osm, .osm.pbf, .osm.bz2.
        If the file is not found, a FileNotFoundError is raised.
        If the file has an invalid extension, an InvalidInputError is raised.

    The function returns the return code of the subprocess.
    """

    input_file = None

    if not filename:
        filename = "to_import"

        input_files = [
            str(RESOURCES_DIR / f"{filename}.osm"),
            str(RESOURCES_DIR / f"{filename}.osm.pbf"),
            str(RESOURCES_DIR / f"{filename}.osm.bz2"),
        ]

        for file in input_files:
            if os.path.exists(file) and is_valid_extension(file):
                input_file = file
    elif os.path.exists(filename):
        input_file = filename

    if not input_file:
        raise FileNotFoundError("There is no valid file to import.")

    style_file_path = str(STYLES_DIR / style_filename)

    return run_osm2pgsql_cmd(
        config, input_file, style_file_path, schema=schema
    ) or post_process_osm_import(style_filename, schema=schema)


# Main flow of the current file, including functions used only within this file


def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process OSM files and interact with PostgreSQL database.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "tag",
        choices=["d", "i", "ie", "s", "r", "sr", "b", "u"],
        metavar="tag",
        help="""
d  : Display OSM file
i  : Display information about OSM file
ie : Display extended information about OSM file
s  : Sort OSM file based on IDs
r  : Renumber object IDs in OSM file
sr : Sort and renumber objects in OSM file
b  : Upload OSM file to PostgreSQL database using osm2pgsql
u  : Extract greatest bounding box from given relation ID of 
     input_file and upload to PostgreSQL database using osm2pgsql""",
    )
    parser.add_argument("input_file", nargs="?", help="Path to input OSM file")
    parser.add_argument(
        "-id", dest="relation_id", nargs="?", help="Relation ID (required for 'b' tag)"
    )
    parser.add_argument(
        "-l",
        dest="style_file",
        default=str(STYLES_DIR / "default.lua"),
        help="Path to style file (optional for 'b', 'u' tag)",
    )
    parser.add_argument(
        "-o",
        dest="output_file",
        help="Path to output file (required for 's', 'r', 'sr' tag)",
    )

    args = parser.parse_args(arg_list)

    return args


def main(arg_list: list[str] | None = None):
    args = parse_args(arg_list)

    if not os.path.exists(args.input_file):
        raise FileNotFoundError(f"File '{args.input_file}' does not exist.")
    elif not is_valid_extension(args.input_file):
        raise InvalidInputError(
            "File must have one of the following extensions: osm, osm.pbf, osm.bz2."
        )
    elif args.style_file:
        if not os.path.exists(args.style_file):
            raise FileNotFoundError(f"File '{args.style_file}' does not exist.")
        elif not args.style_file.endswith(".lua"):
            raise InvalidInputError("File must have the '.lua' extension.")

    match args.tag:
        case "d" | "i" | "ie":
            # Display content or (extended) information of OSM file
            run_osmium_cmd(args.tag, args.input_file)

        case "s" | "r" | "sr":
            # Sort, renumber OSM file or do both
            if not args.output_file:
                raise MissingInputError(
                    "An output file must be specified with '-o' tag."
                )
            run_osmium_cmd(args.tag, args.input_file, args.output_file)

        case "u":
            # Upload OSM file to PostgreSQL database
            run_osm2pgsql_cmd(config, args.input_file, args.style_file)
        case "b":
            # Extract bounding box based on relation ID and import to PostgreSQL
            if not args.relation_id:
                raise MissingInputError("Existing relation ID must be specified.")

            min_lon, min_lat, max_lon, max_lat = extract_bbox(args.relation_id)
            coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            run_osm2pgsql_cmd(config, args.input_file, args.style_file, coords)


if __name__ == "__main__":
    main()
