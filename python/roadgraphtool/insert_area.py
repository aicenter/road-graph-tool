import json

import psycopg2


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
        (id, name, description, json.dumps(geom)),
    )
