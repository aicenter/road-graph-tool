import logging
import sqlalchemy
import geopandas as gpd

from db import get_sql_alchemy_engine_str


def get_map_nodes_from_db(config: dict, server_port, area_id : int) -> gpd.GeoDataFrame:
    logging.info("Fetching nodes from db")
    sql = f"""
    DROP TABLE IF EXISTS demand_nodes;

    CREATE TEMP TABLE demand_nodes(
        id int,
        db_id bigint,
        x float,
        y float,
        geom geometry
    );

    INSERT INTO demand_nodes
    SELECT * FROM select_network_nodes_in_area({area_id}::smallint);

    SELECT
        id,
        db_id,
        x,
        y,
        geom
    FROM demand_nodes
    """
    sql_alchemy_engine_str = get_sql_alchemy_engine_str(config, server_port)
    logging.info("Starting sql_alchemy connection")
    sqlalchemy_engine = sqlalchemy.create_engine(sql_alchemy_engine_str)

    return gpd.read_postgis(sql, sqlalchemy_engine)
