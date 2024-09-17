import os
import pytest
import pandas as pd
import geopandas as gpd
from shapely import LineString
from shapely.geometry import Point

from roadgraphtool import map
from roadgraphtool.db import db

TEST_SCHEMA = 'TEST_MAP'
DEFAULT_SCHEMA = 'public'


@pytest.fixture
def config():
    return {
        'area_dir': './',
        'area_id': 99,
        'map': {
            'path': './map',
            'SRID': 4326,
            'SRID_plane': 32618,
        }
    }


@pytest.fixture
def sample_nodes():
    return gpd.GeoDataFrame({
        'id': [0, 1],
        'db_id': [1, 2],
        'x': [1, 2],
        'y': [1, 2],
        'geometry': [Point(1, 1), Point(2, 2)],
    }, crs="EPSG:4326")


@pytest.fixture
def sample_edges():
    return gpd.GeoDataFrame({
        'u': [0],
        'v': [1],
        'db_id_from': [1],
        'db_id_to': [2],
        'speed': 32,
        'length': [1.4142],
        'geometry': LineString(((1, 1), (2, 2)))
    }, crs="EPSG:4326")


@pytest.fixture
def shapefile_dir(tmp_path):
    return tmp_path / "shapefiles"


@pytest.fixture
def csv_dir(tmp_path):
    return tmp_path


def test_save_graph_shapefile(sample_nodes, sample_edges, shapefile_dir):
    map._save_graph_shapefile(sample_nodes, sample_edges, str(shapefile_dir))

    nodes_shapefile = shapefile_dir / "nodes.shp"
    edges_shapefile = shapefile_dir / "edges.shp"

    assert nodes_shapefile.exists(), "Nodes shapefile was not created."
    assert edges_shapefile.exists(), "Edges shapefile was not created."

    loaded_nodes = gpd.read_file(nodes_shapefile)
    loaded_edges = gpd.read_file(edges_shapefile)

    pd.testing.assert_frame_equal(sample_nodes, loaded_nodes)
    pd.testing.assert_frame_equal(sample_edges, loaded_edges)


def test_save_map_csv(sample_nodes, sample_edges, csv_dir):
    map._save_map_csv(str(csv_dir), sample_nodes, sample_edges)

    nodes_csv = csv_dir / "nodes.csv"
    edges_csv = csv_dir / "edges.csv"

    assert nodes_csv.exists(), "Nodes CSV was not created."
    assert edges_csv.exists(), "Edges CSV was not created."

    loaded_nodes = pd.read_csv(nodes_csv, sep='\t')
    loaded_edges = pd.read_csv(edges_csv, sep='\t')

    sample_nodes['geometry'] = sample_nodes['geometry'].apply(lambda geom: geom.wkt)
    sample_edges['geometry'] = sample_edges['geometry'].apply(lambda geom: geom.wkt)

    pd.testing.assert_frame_equal(sample_nodes, loaded_nodes)
    pd.testing.assert_frame_equal(sample_edges, loaded_edges)


def test_get_map_mocker(mocker, config, sample_nodes, sample_edges, shapefile_dir, csv_dir):
    mocker.patch('roadgraphtool.map._get_map_from_db', return_value=(sample_nodes, sample_edges))
    mocker.patch('roadgraphtool.map._get_map', return_value=(sample_nodes, sample_edges))
    mocker.patch('roadgraphtool.map._save_graph_shapefile')
    mocker.patch('roadgraphtool.map._save_map_csv')

    nodes, edges = map.get_map(config)

    assert not nodes.empty, "Nodes should not be empty."
    assert not edges.empty, "Edges should not be empty."
    assert len(nodes) == 2, "Nodes count mismatch."
    assert len(edges) == 1, "Edges count mismatch."

    map._save_graph_shapefile.assert_called_once_with(nodes, edges,
                                                      os.path.join(config['map']['path'], 'shapefiles'))
    map._save_map_csv.assert_called_once_with(config['map']['path'], nodes, edges)


def delete_component_data():
    sql_delete_component_data = """
            DELETE FROM component_data 
            WHERE (component_id, node_id, area) IN (
                (0, 100, 99),
                (0, 101, 99)
            );
            """
    db.execute_sql_in_schema(sql_delete_component_data, TEST_SCHEMA)


def delete_nodes():
    sql_delete_nodes = """
        DELETE FROM nodes 
        WHERE id IN (100, 101);
        """
    db.execute_sql_in_schema(sql_delete_nodes, TEST_SCHEMA)


def delete_edges():
    sql_delete_edge = """
        DELETE FROM edges 
        WHERE id = 1;
        """
    db.execute_sql_in_schema(sql_delete_edge, TEST_SCHEMA)


def delete_area():
    sql_delete_area = """
        DELETE FROM areas 
        WHERE id = 99;
        """
    db.execute_sql_in_schema(sql_delete_area, TEST_SCHEMA)


def test_if_schema_exists():
    db.create_schema(TEST_SCHEMA)
    db.copy_all_tables_to_new_schema(DEFAULT_SCHEMA, TEST_SCHEMA)


def test_get_nodes_edges_empty_db(config):
    delete_component_data()
    delete_edges()
    delete_nodes()
    delete_area()

    db.execute_sql(f"SET search_path TO {TEST_SCHEMA}, public;")
    nodes = map.get_map_nodes_from_db(config['area_id'])
    assert nodes.empty, "Expected no nodes in the database."

    with pytest.raises(Exception) as exc_info:
        map.get_map_edges_from_db(config)
    db.execute_sql(f"SET search_path TO public;")

    assert exc_info.type is Exception
    assert exc_info.value.args[0] == "No edges selected"


def test_get_nodes_edges_empty_component_data(config):
    delete_component_data()

    # set up test_db
    sql_insert_area = """
        INSERT INTO areas (id, name) 
        VALUES (99, 'Test_get_map')
        ON CONFLICT (id) DO NOTHING;
        """
    db.execute_sql_in_schema(sql_insert_area, TEST_SCHEMA)

    sql_insert_nodes = """
        INSERT INTO nodes (id, area, geom, contracted) 
        VALUES
            (100, 99, ST_SetSRID(ST_MakePoint(0, 0), 4326), false),
            (101, 99, ST_SetSRID(ST_MakePoint(1, 1), 4326), false)
        ON CONFLICT (id) DO NOTHING;
        """

    db.execute_sql_in_schema(sql_insert_nodes, TEST_SCHEMA + ', public')

    sql_insert_edge = """
        INSERT INTO edges ("from", "to", id, geom, area, speed) 
        VALUES
            (100, 101, 1, ST_GeomFromText('MULTILINESTRING((0 0, 1 1))', 4326), 99, 25)
        ON CONFLICT (id) DO NOTHING;
        """

    db.execute_sql_in_schema(sql_insert_edge, TEST_SCHEMA + ', public')

    db.execute_sql(f"SET search_path TO {TEST_SCHEMA}, public;")
    nodes = map.get_map_nodes_from_db(config['area_id'])
    assert nodes.empty, "Expected no nodes."

    with pytest.raises(Exception) as exc_info:
        map.get_map_edges_from_db(config)
    db.execute_sql(f"SET search_path TO public;")

    assert exc_info.type is Exception
    assert exc_info.value.args[0] == "No edges selected"


def test_get_nodes_edges_from_db(config):
    # set up component_data
    sql_insert_component_data = """
        INSERT INTO component_data (component_id, node_id, area) 
        VALUES
            (0, 100, 99),
            (0, 101, 99)
        ON CONFLICT (node_id, area) DO NOTHING;
        """
    db.execute_sql_in_schema(sql_insert_component_data, TEST_SCHEMA)

    db.execute_sql(f"SET search_path TO {TEST_SCHEMA}, public;")
    nodes = map.get_map_nodes_from_db(config['area_id'])
    edges = map.get_map_edges_from_db(config)
    db.execute_sql(f"SET search_path TO public;")

    assert len(nodes) == 2, "Expected 2 nodes from the database."
    assert len(edges) == 1, "Expected 1 edge from the database."


def test_nodes_edges_data_consistency(config):
    db.execute_sql(f"SET search_path TO {TEST_SCHEMA}, public;")
    nodes = map.get_map_nodes_from_db(config['area_id'])
    edges = map.get_map_edges_from_db(config)
    db.execute_sql(f"SET search_path TO public;")

    # Check if every edge's db_id_from and db_id_to exist in the nodes' db_id
    for index, edge in edges.iterrows():
        assert edge['db_id_from'] in nodes['db_id'].values, f"Edge {index} has invalid db_id_from."
        assert edge['db_id_to'] in nodes['db_id'].values, f"Edge {index} has invalid db_id_to."
