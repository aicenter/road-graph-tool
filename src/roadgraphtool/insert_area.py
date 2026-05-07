import argparse
import geojson
from pathlib import Path
import sys
import logging
from typing import Optional, Union, Dict, Any
import shapely
import shapely.geometry as geometry
from shapely.ops import linemerge, unary_union, polygonize
from roadgraphtool import db
from roadgraphtool.config import parse_config_file
from roadgraphtool.overpass_client import elements_by_type, query_json_from_config



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

def get_boundary_from_overpass(config: Dict[str, Any]) -> geometry.MultiPolygon:
    if not hasattr(config.area_insert.boundary_source, "admin_boundary_name"):
        raise ValueError("""
        Admin boundary name not specified in config. Should be in config.area_insert.boundary_source.admin_boundary_name.
        """)
    admin_boundary_name = config.area_insert.boundary_source.admin_boundary_name
    # Query administrative boundary relation ways with geometry.
    # We avoid relying on client-side XML parsing and instead parse Overpass JSON.
    query = f"""
    [out:json][timeout:25];
    rel["boundary"="administrative"]["name"="{admin_boundary_name}"]->.r;
    way(r.r);
    out geom;
    """
    overpass_json = query_json_from_config(config, query, build=False)
    by_type = elements_by_type(overpass_json)
    ways = by_type["way"]

    if not ways:
        logging.error(f"The area '{admin_boundary_name}' was not found in Overpass (no boundary ways returned).")
        raise Exception(f"The area '{admin_boundary_name}' was not found in Overpass.")

    lss = []  # convert ways to linestrings
    for way in ways:
        geom_coords = way.get("geometry", [])
        if not geom_coords:
            continue
        ls_coords = [(float(c["lon"]), float(c["lat"])) for c in geom_coords if "lon" in c and "lat" in c]
        if len(ls_coords) >= 2:
            lss.append(geometry.LineString(ls_coords))

    if not lss:
        raise Exception(f"The area '{admin_boundary_name}' was found but no geometry could be constructed.")

    merged = linemerge([*lss])  # merge LineStrings
    borders = unary_union(merged)  # linestrings to a MultiLineString
    polygons = list(polygonize(borders))
    return geometry.MultiPolygon(polygons)

def get_boundary_geojson(config):
    if not hasattr(config.area_insert, "boundary_source"):
        raise ValueError("""
        Boundary source not specified in config. Should be in config.area_insert.boundary_source. 
        """)
    boundary_source = config.area_insert.boundary_source

    if not hasattr(boundary_source, "type"):
        raise ValueError("""
        Boundary source type not specified in config. Should be in config.area_insert.boundary_source.type. Has to be
        one of: "geojson_file", "overpass", "inline"
        """)

    if boundary_source.type == "geojson_file":

        if not hasattr(boundary_source, "file_path"):
            raise ValueError("""
            File path not specified in config. Should be in config.area_insert.boundary_source.file_path.
            """)
        file_path = boundary_source.file_path
        return read_geojson_file(file_path)
    if boundary_source.type == "overpass":
        return geojson.loads(shapely.to_geojson(get_boundary_from_overpass(config)))
    if boundary_source.type == "convex_hull":
        if not hasattr(boundary_source, "buffer_in_m"):
            raise ValueError("""
            Buffer in meters not specified in config. Should be in config.area_insert.boundary_source.buffer_in_m.
            """)
        buffer_in_m = boundary_source.buffer_in_m
        query = (f"""
            SELECT ST_asgeojson(st_multi(st_transform(st_buffer(st_convexhull(st_collect(st_transform(geom, {config.srid}))), 
{buffer_in_m}), 
            4326))) 
            FROM {config.importer.schema}.nodes;""")
        result = db.execute_sql_and_fetch_all_rows(query)

        return result[0][0]

def genereate_area(config, description: str = None) -> int:
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
