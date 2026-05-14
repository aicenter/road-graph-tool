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


def _overpass_rel_admin_level_if_fragment(boundary_source: Any) -> str:
    """
    Build an Overpass eval filter (if: ...) for administrative relations by admin_level.

    When ``min_admin_level`` and/or ``max_admin_level`` is set on ``boundary_source``,
    relations must satisfy ``t["admin_level"] >= min`` (inclusive lower bound) and/or
    ``t["admin_level"] <= max`` (inclusive upper bound), matching Overpass patterns such as
    ``rel(if: t["admin_level"] > 4)[...]``. If neither key is present, returns an empty string.
    """
    has_min = hasattr(boundary_source, "min_admin_level") and boundary_source.min_admin_level is not None
    has_max = hasattr(boundary_source, "max_admin_level") and boundary_source.max_admin_level is not None
    if not has_min and not has_max:
        return ""
    conditions: list[str] = []
    min_v: Optional[int] = None
    max_v: Optional[int] = None
    if has_min:
        min_v = int(boundary_source.min_admin_level)
        conditions.append(f't["admin_level"] >= {min_v}')
    if has_max:
        max_v = int(boundary_source.max_admin_level)
        conditions.append(f't["admin_level"] <= {max_v}')
    if min_v is not None and max_v is not None and max_v <= min_v:
        raise ValueError(
            "boundary_source.max_admin_level must be greater than min_admin_level "
            "(need admin_level strictly greater than min and at most max)."
        )
    return f'(if: {" && ".join(conditions)})'


def get_boundary_from_overpass(config: Dict[str, Any]) -> geometry.MultiPolygon:
    if not hasattr(config.area_insert.boundary_source, "admin_boundary_name"):
        raise ValueError("""
        Admin boundary name not specified in config. Should be in config.area_insert.boundary_source.admin_boundary_name.
        """)
    admin_boundary_name = config.area_insert.boundary_source.admin_boundary_name

    # Optional: restrict the search to one or more enclosing administrative areas (outer -> inner).
    # Config shape:
    # area_insert:
    #   boundary_source:
    #     enclosing_areas: ["Country", "State", "County"]
    #     min_admin_level / max_admin_level: optional; add rel(if: t["admin_level"] ...) filter (see
    #     _overpass_rel_admin_level_if_fragment).
    boundary_source = config.area_insert.boundary_source
    admin_if = _overpass_rel_admin_level_if_fragment(boundary_source)

    enclosing_areas = []
    if hasattr(boundary_source, "enclosing_areas"):
        enclosing_areas = boundary_source.enclosing_areas or []
        if not isinstance(enclosing_areas, list):
            raise ValueError("""
            enclosing_areas must be a list of area names (strings). Example:
            config.area_insert.boundary_source.enclosing_areas: ["France", "Occitanie"]
            """)
        for a in enclosing_areas:
            if not isinstance(a, str):
                raise ValueError("Each enclosing_areas entry must be a string area name.")
    # Query administrative boundary relation ways with geometry.
    # We avoid relying on client-side XML parsing and instead parse Overpass JSON.
    #
    # If enclosing_areas is provided, we progressively narrow the search by:
    # - selecting the outermost enclosing area as an Overpass "area"
    # - then selecting each next enclosing boundary relation within that area
    # - converting that relation into an area (map_to_area) for further narrowing
    # - finally selecting the target admin boundary relation within the final area
    if enclosing_areas:
        parts = [
            "[out:json][timeout:25];",
            f'area["boundary"="administrative"]["name"="{enclosing_areas[0]}"];',
        ]
        # Narrow further, if more than one enclosing area name is provided
        for enclosing_name in enclosing_areas[1:]:
            parts.append(f'area["boundary"="administrative"]["name"="{enclosing_name}"];')

        parts.append(
            f'rel(area){admin_if}["boundary"="administrative"]["name"="{admin_boundary_name}"]->.r;'
        )
        parts.append("way(r.r);")
        parts.append("out geom;")
        query = "\n".join(parts)
    else:
        query = f"""
        [out:json][timeout:25];
        rel{admin_if}["boundary"="administrative"]["name"="{admin_boundary_name}"]->.r;
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

    allow_multipolygon = False
    if hasattr(config, "area_insert") and hasattr(config.area_insert, "allow_multipolygon"):
        allow_multipolygon = bool(config.area_insert.allow_multipolygon)

    if not allow_multipolygon and len(polygons) != 1:
        raise Exception(
            f"Overpass boundary '{admin_boundary_name}' produced {len(polygons)} polygons (multipolygon). "
            f"Set config.area_insert.allow_multipolygon: true to allow this."
        )
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
        if not hasattr(config, "road_import") or not hasattr(config.road_import, "schema"):
            raise ValueError(
                "convex_hull boundary requires config.road_import.schema (staging schema with nodes)."
            )
        if not hasattr(boundary_source, "buffer_in_m"):
            raise ValueError("""
            Buffer in meters not specified in config. Should be in config.area_insert.boundary_source.buffer_in_m.
            """)
        buffer_in_m = boundary_source.buffer_in_m
        query = (f"""
            SELECT ST_asgeojson(st_multi(st_transform(st_buffer(st_convexhull(st_collect(st_transform(geom, {config.srid}))), 
{buffer_in_m}), 
            4326))) 
            FROM {config.road_import.schema}.nodes;""")
        result = db.execute_sql_and_fetch_all_rows(query)

        return result[0][0]

def genereate_area(config, description: str = None) -> int:
    boundary_geom = get_boundary_geojson(config)

    area_id = insert_area(name=config.area_insert.name, description=description, geom=boundary_geom)

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
