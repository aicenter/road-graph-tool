import argparse
import geojson
from pathlib import Path
import sys
import logging
from typing import Optional, Union
import overpy
import shapely
import shapely.geometry as geometry
from shapely.ops import linemerge, unary_union, polygonize
from roadgraphtool import db
from roadgraphtool.config import parse_config_file



def insert_area(
    name: str,
    id: Optional[int] = None,
    description: Optional[str] = None,
    geom: Optional[Union[geojson.Feature, geojson.FeatureCollection]] = None
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
    elif isinstance(geom, geojson.MultiPolygon):
        geom = f"'{geojson.dumps(geom)}'"
    elif isinstance(geom, geojson.Feature):
        geom = f"'{geojson.dumps(geom.geometry)}'"
    elif not isinstance(geom, str):
        geom = f"'{geojson.dumps(geom[0].geometry)}'"

    logging.info("Inserting area '%s' into the database.", name)

    sql = f"SELECT insert_area('{name}', {geom}, {id}, '{description}')"

    if geom is not None:
        # would not log the geom if it is too long
        logging.info(f"Executing SQL query: SELECT insert_area('{name}', geom was provided, {id}, '{description}')")
        # TODO: if logging.DEBUG:
        # logging.debug(f"Executing SQL query: SELECT insert_area('{name}', {geom}, {id}, '{description}')")
    else:
        logging.info(f"Executing SQL query: {sql}")

    ret = db.db.execute_sql_and_fetch_all_rows(sql)
    return ret[0][0]


def read_geojson_file(file_path: str) -> Union[geojson.Feature, geojson.FeatureCollection]:
    """
    Read a JSON file and return its contents as a dictionary.

    Args:
    file_path (str): The path to the JSON file

    Returns:
    dict: The contents of the JSON file as a dictionary
    """
    try:
        with open(file_path, "r") as file:
            return geojson.load(file)
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
    parser.add_argument(
        "-c", "--config", required=False, default=None, help="Config", )
    return parser.parse_args()

def get_boundary_from_overpass(area_name: str) -> geometry.MultiPolygon:
    api = overpy.Overpass()

    # try to find the area by name and english name case-insensitive
    # query = f"""[out:json][timeout:25];
    # (rel["name"~"^{area_name}$",i];rel["name:en"~"^{area_name}$",i];);
    # out body;
    # >;
    # out skel qt; """
    query = f"""[out:json][timeout:25];
area["name"="{area_name}"];
node(pivot);
out geom;
"""

    result = api.query(query)

    relations = result.relations
    if len(relations) == 0:
        logging.error(f"The area '{area_name}' was not found in Overpass.")
        raise Exception(f"The area '{area_name}' was not found in Overpass.")
    elif len(relations) > 1:
        logging.warning(f"More than one area with the name '{area_name}' was found in Overpass. Using the first one.")
    area_relation = relations[0]

    lss = []  # convert ways to linestrings
    for ii_w, way in enumerate(area_relation.members):
        ls_coords = []

        for coord in way.geometry:
            ls_coords.append((coord.lon, coord.lat))  # create a list of node coordinates

        lss.append(geometry.LineString(ls_coords))  # create a LineString from coords

    merged = linemerge([*lss])  # merge LineStrings
    borders = unary_union(merged)  # linestrings to a MultiLineString
    polygons = list(polygonize(borders))
    return geometry.MultiPolygon(polygons)

def get_boundary_geojson(config):
    boundary_source = config.area.boundary_source
    if boundary_source == "geojson_file":
        return read_geojson_file(config.importer.geom)
    if boundary_source == "overpass":
        return geojson.loads(shapely.to_geojson(get_boundary_from_overpass(config.area.name)))
    if hasattr(boundary_source, "convex_hull"):
        query = (f"""
            SELECT ST_asgeojson(st_multi(st_transform(st_buffer(st_convexhull(st_collect(st_transform(geom, {config.srid}))), 
{boundary_source.convex_hull.buffer_in_m}), 
            4326))) 
            FROM {config.importer.schema}.nodes;""")
        result = db.execute_sql_and_fetch_all_rows(query)

        return result[0][0]

def genereate_area(config, description: str = None) -> int:
    boundary_geom = None

    if hasattr(config.area, "boundary_source"):
        boundary_geom = get_boundary_geojson(config)

    area_id = insert_area(name=config.area.name, description=description, geom=boundary_geom)

    return area_id


if __name__ == "__main__":
    args = parse_arguments()

    # Read the GeoJSON file
    area_geojson = read_geojson_file(args.file)
    
    config = parse_config_file(Path(args.config))
    db.init_db(config)
    # inserting area to db
    try:
        insert_area(name=args.name, id=args.id, description=args.description, geom=area_geojson)
        print(f"Area '{args.name}' inserted successfully.")
    except Exception as e:
        print(f"Error inserting area: {e}")
