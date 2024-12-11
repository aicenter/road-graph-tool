import argparse
import json
import sys
import logging
from typing import Optional

from .db import db


def insert_area(
    name: str,
    id: Optional[int] = None,
    description: Optional[str] = None,
    geom: Optional[dict] = None
) -> int:
    """
    Insert a new area into the areas table.

    Args:
    id (int): The ID of the area
    name (str): The name of the area
    description (str): The description of the area
    geom (dict): The geometry of the area as a GeoJSON dictionary

    Returns:
    None
    """

    # set defaults
    if id is None:
        id = "NULL"

    if description is None:
        description = ""

    if geom is None:
        geom = "NULL"
    else:
        geom = f"'{json.dumps(geom)}'"

    logging.info("Inserting area '%s' into the database.", name)

    sql = f"SELECT insert_area('{name}', {geom}, {id}, '{description}')"

    logging.info("Executing SQL query: %s", sql)

    ret = db.execute_sql_and_fetch_all_rows(sql)
    return ret[0][0]


def read_json_file(file_path: str) -> dict:
    """
    Read a JSON file and return its contents as a dictionary.

    Args:
    file_path (str): The path to the JSON file

    Returns:
    dict: The contents of the JSON file as a dictionary
    """
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print(f"Error: The file {file_path} is not a valid JSON file.")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
    argparse.Namespace: The parsed arguments
    """
    parser = argparse.ArgumentParser(description="Insert an area into the database.")
    parser.add_argument("-n", "--name", required=True, help="The name of the area")
    parser.add_argument(
        "-f", "--file", required=True, help="The relative path to the GeoJSON file"
    )
    parser.add_argument(
        "-i", "--id", type=int, required=False, default=None, help="The id of the area"
    )
    parser.add_argument(
        "-d", "--description", required=False, default=None, help="The description of the area", )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Read the GeoJSON file
    geojson = read_json_file(args.file)

    # inserting area to db
    try:
        insert_area(name=args.name, id=args.id, description=args.description, geom=geojson)
        print(f"Area '{args.name}' inserted successfully.")
    except Exception as e:
        print(f"Error inserting area: {e}")
