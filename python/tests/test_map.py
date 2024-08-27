import os
import pytest
import pandas as pd
import geopandas as gpd

from roadgraphtool import map
from shapely import LineString
from shapely.geometry import Point


@pytest.fixture
def config():
    return {
        'area_dir': './',
        'area_id': 1,
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


def test_get_map(mocker, config, sample_nodes, sample_edges, shapefile_dir, csv_dir):
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
