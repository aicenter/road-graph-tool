import argparse
import json
import sys

import psycopg2
from db import db


def insert_area(
    cursor: psycopg2.cursor, id: int, name: str, description: str, geom: dict
):
    """
    Insert a new area into the areas table.

    Args:
    cursor: psycopg2 cursor object
    id (int): The ID of the area
    name (str): The name of the area
    description (str): The description of the area
    geom (dict): The geometry of the area as a GeoJSON dictionary

    Returns:
    None
    """
    cursor.execute(
        "SELECT insert_area(%s, %s, %s, %s)",
        (name, json.dumps(geom), id, description),
    )


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
        "-d",
        "--description",
        required=False,
        default=None,
        help="The description of the area",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Read the GeoJSON file
    geojson = read_json_file(args.file_path)

    # Establish database connection
    conn = db._psycopg2_connection

    try:
        with conn.cursor() as cursor:
            # For this example, we're using a placeholder ID and description
            # You might want to generate these dynamically or accept them as additional arguments
            insert_area(
                cursor,
                id=args.id,
                name=args.name,
                description=args.description,
                geom=geojson,
            )
        conn.commit()
        print(f"Area '{args.name}' inserted successfully.")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Error inserting area: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
