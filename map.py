import logging
import sqlalchemy
import geopandas as gpd
from credentials_config import CREDENTIALS


def get_sql_alchemy_engine_str(config: CREDENTIALS, server_port):
    sql_alchemy_engine_str = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'.format(
        user=config.username,
        password=config.db_password,
        host=config.db_host,
        port=server_port,
        dbname=config.db_name)

    return sql_alchemy_engine_str


def get_map_edges_from_db(config, server_port, area_id: int, area_srid: int) -> gpd.GeoDataFrame:
    pass


def get_map_nodes_from_db(config, server_port, area_id: int) -> gpd.GeoDataFrame:
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
