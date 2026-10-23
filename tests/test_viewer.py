import json
import types

import geopandas as gpd
import numpy as np
import pyogrio
import pytest
from shapely import LineString, Point

from roadgraphtool import viewer


@pytest.fixture
def nodes():
    # ids intentionally not in row order
    return gpd.GeoDataFrame({
        'id': [2, 0, 1],
        'db_id': [30, 10, 20],
        'x': [14.42, 14.40, 14.41],
        'y': [50.07, 50.05, 50.06],
        'geom': [Point(14.42, 50.07), Point(14.40, 50.05), Point(14.41, 50.06)],
    }, geometry='geom', crs="EPSG:4326")


@pytest.fixture
def edges():
    # edges intentionally not sorted by u
    return gpd.GeoDataFrame({
        'u': [1, 0, 2, 1],
        'v': [2, 1, 0, 0],
        'db_id_from': [20, 10, 30, 20],
        'db_id_to': [30, 20, 10, 10],
        'length': [1500.04, 1400.0, 2900.0, 1400.0],
        'geom': [
            LineString([(14.41, 50.06), (14.42, 50.07)]),
            LineString([(14.40, 50.05), (14.41, 50.06)]),
            LineString([(14.42, 50.07), (14.40, 50.05)]),
            LineString([(14.41, 50.06), (14.40, 50.05)]),
        ],
    }, geometry='geom', crs="EPSG:4326")


@pytest.fixture
def config(tmp_path):
    return types.SimpleNamespace(
        viewer=types.SimpleNamespace(activated=True, dir=tmp_path / 'viewer', title='Test network', min_zoom=10, max_zoom=14)
    )


def _read_graph(path, node_count, edge_count):
    data = path.read_bytes()
    assert len(data) == 16 * node_count + 4 * (node_count + 1) + 12 * edge_count
    offset = 0

    def take(dtype, length):
        nonlocal offset
        array = np.frombuffer(data, dtype=dtype, count=length, offset=offset)
        offset += length * array.itemsize
        return array

    return (
        take('<f8', node_count),
        take('<f4', 2 * node_count).reshape(-1, 2),
        take('<u4', node_count + 1),
        take('<u4', edge_count),
        take('<f4', edge_count),
        take('<u4', edge_count),
    )


def test_write_graph(tmp_path, nodes, edges):
    edges['eid'] = edges.index
    path = tmp_path / 'graph.bin'
    viewer.write_graph(nodes, edges, path)

    db_ids, coords, offsets, targets, lengths, edge_ids = _read_graph(path, 3, 4)
    np.testing.assert_array_equal(db_ids, [10, 20, 30])
    np.testing.assert_allclose(coords, [[14.40, 50.05], [14.41, 50.06], [14.42, 50.07]], rtol=1e-6)
    np.testing.assert_array_equal(offsets, [0, 1, 3, 4])
    np.testing.assert_array_equal(edge_ids, [1, 0, 3, 2])
    np.testing.assert_array_equal(targets, [1, 2, 0, 0])
    np.testing.assert_allclose(lengths, [1400.0, 1500.04, 1400.0, 2900.0], rtol=1e-6)


def test_build_viewer(config, nodes, edges):
    viewer.build_viewer(config, nodes, edges)
    viewer_dir = config.viewer.dir

    for static_file in viewer.STATIC_DIR.iterdir():
        assert (viewer_dir / static_file.name).read_bytes() == static_file.read_bytes()

    build_info = json.loads((viewer_dir / 'build.json').read_text(encoding='utf-8'))
    assert build_info['title'] == 'Test network'
    assert build_info['node_count'] == 3
    assert build_info['edge_count'] == 4
    np.testing.assert_allclose(build_info['bounds'], [14.40, 50.05, 14.42, 50.07])

    _, _, _, _, lengths, _ = _read_graph(viewer_dir / 'graph.bin', 3, 4)
    assert lengths[1] == pytest.approx(1500.0)  # rounded to 0.1 m

    tile_edges = pyogrio.read_dataframe(viewer_dir / 'edges.pmtiles', layer='edges', ZOOM_LEVEL=14)
    assert sorted(tile_edges['eid'].unique()) == [0, 1, 2, 3]
    tile_nodes = pyogrio.read_dataframe(viewer_dir / 'nodes.pmtiles', layer='nodes', ZOOM_LEVEL=14)
    assert sorted(tile_nodes['id'].unique()) == [0, 1, 2]


def test_build_viewer_fetches_map_when_not_provided(mocker, config, nodes, edges):
    get_map = mocker.patch('roadgraphtool.export.get_map_from_db', return_value=(nodes, edges))
    viewer.build_viewer(config)
    get_map.assert_called_once_with(config)
    assert (config.viewer.dir / 'graph.bin').exists()
