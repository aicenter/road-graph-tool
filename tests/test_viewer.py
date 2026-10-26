import json
import types

import geopandas as gpd
import numpy as np
import pyogrio
import pytest
from shapely import LineString, MultiLineString, Point

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
        viewer=types.SimpleNamespace(
            activated=True, dir=tmp_path / 'viewer', title='Test network', min_zoom=10, max_zoom=14, processes=2
        )
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


def _read_shapes(path, shape_count, vertex_count):
    data = path.read_bytes()
    assert len(data) == 12 * shape_count + 4 + 8 * vertex_count
    eids = np.frombuffer(data, '<i4', shape_count, 0)
    eids2 = np.frombuffer(data, '<i4', shape_count, 4 * shape_count)
    offsets = np.frombuffer(data, '<u4', shape_count + 1, 8 * shape_count)
    coords = np.frombuffer(data, '<f4', 2 * vertex_count, 12 * shape_count + 4).reshape(-1, 2)
    return eids, eids2, offsets, coords


def test_write_shapes(tmp_path, nodes):
    edges = gpd.GeoDataFrame({
        'u': [0, 1],
        'v': [1, 2],
        'geom': [
            LineString([(14.40, 50.05), (14.405, 50.056), (14.41, 50.06)]),
            # stored in the opposite direction than the edge goes
            LineString([(14.42, 50.07), (14.41, 50.06)]),
        ],
    }, geometry='geom', crs="EPSG:4326")
    edges['eid'] = edges.index
    features = edges[['eid', 'geom']].assign(eid2=[5, -1])
    path = tmp_path / 'shapes.bin'

    assert viewer.write_shapes(features, nodes, edges, path) == 5

    eids, eids2, offsets, coords = _read_shapes(path, 2, 5)
    np.testing.assert_array_equal(eids, [0, 1])
    np.testing.assert_array_equal(eids2, [5, -1])
    np.testing.assert_array_equal(offsets, [0, 3, 5])
    np.testing.assert_allclose(
        coords, [[14.40, 50.05], [14.405, 50.056], [14.41, 50.06], [14.41, 50.06], [14.42, 50.07]], rtol=1e-7
    )


def test_write_shapes_joins_parts(tmp_path):
    # the parts of an edge geometry in the database are in no particular order and direction
    nodes = gpd.GeoDataFrame({
        'id': [0, 1, 2, 3],
        'db_id': [10, 20, 30, 40],
        'geom': [Point(0, 0), Point(3, 0), Point(0, 1), Point(2, 1)],
    }, geometry='geom', crs="EPSG:4326")
    edges = gpd.GeoDataFrame({
        'u': [0, 2],
        'v': [1, 3],
        'geom': [
            # 0 -> 1 along x = 0..3
            MultiLineString([[(2, 0), (3, 0)], [(1, 0), (0, 0)], [(1, 0), (2, 0)]]),
            # 2 -> 3 passing through (1, 1) twice around the loop (1, 1), (1, 2), (0.5, 2)
            MultiLineString([[(1, 1), (2, 1)], [(1, 2), (1, 1)], [(0, 1), (1, 1)], [(1, 2), (0.5, 2)],
                             [(0.5, 2), (1, 1)]]),
        ],
    }, geometry='geom', crs="EPSG:4326")
    edges['eid'] = edges.index
    features = edges[['eid', 'geom']].assign(eid2=-1)
    path = tmp_path / 'shapes.bin'

    assert viewer.write_shapes(features, nodes, edges, path) == 10

    _, _, offsets, coords = _read_shapes(path, 2, 10)
    np.testing.assert_array_equal(coords[offsets[0]:offsets[1]], [[0, 0], [1, 0], [2, 0], [3, 0]])
    second = coords[offsets[1]:offsets[2]]
    np.testing.assert_array_equal(second[[0, 1, -2, -1]], [[0, 1], [1, 1], [1, 1], [2, 1]])
    assert {tuple(c) for c in second[2:4]} == {(1, 2), (0.5, 2)}


def test_write_shapes_keeps_zero_length_geometries(tmp_path):
    # two distinct nodes at the same position
    nodes = gpd.GeoDataFrame({'id': [0, 1], 'db_id': [10, 20], 'geom': [Point(1, 1), Point(1, 1)]}, geometry='geom',
                             crs="EPSG:4326")
    edges = gpd.GeoDataFrame({
        'u': [0, 1],
        'v': [1, 0],
        'geom': [LineString([(1, 1), (1, 1)]), MultiLineString([[(1, 1), (1, 1)], [(1, 1), (1, 1)]])],
    }, geometry='geom', crs="EPSG:4326")
    edges['eid'] = edges.index
    path = tmp_path / 'shapes.bin'

    vertex_count = viewer.write_shapes(edges[['eid', 'geom']].assign(eid2=-1), nodes, edges, path)

    _, _, offsets, coords = _read_shapes(path, 2, vertex_count)
    assert np.all(np.diff(offsets) >= 2)
    np.testing.assert_array_equal(coords, np.ones((vertex_count, 2)))


def test_write_shapes_rejects_disconnected_parts(tmp_path, nodes):
    edges = gpd.GeoDataFrame({
        'u': [0], 'v': [1],
        'geom': [MultiLineString([[(14.40, 50.05), (14.403, 50.052)], [(14.407, 50.057), (14.41, 50.06)]])],
    }, geometry='geom', crs="EPSG:4326")
    edges['eid'] = edges.index
    with pytest.raises(ValueError, match="edge 0"):
        viewer.write_shapes(edges[['eid', 'geom']].assign(eid2=-1), nodes, edges, tmp_path / 'shapes.bin')


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

    assert build_info['shape_count'] == 3
    assert build_info['vertex_count'] == 6
    eids, eids2, _, _ = _read_shapes(viewer_dir / 'shapes.bin', 3, 6)
    np.testing.assert_array_equal(eids, [0, 1, 2])
    np.testing.assert_array_equal(eids2, [-1, 3, -1])

    # all zoom levels merged into one file; edges 1 (0 -> 1) and 3 (1 -> 0) are one two-way feature
    for zoom in range(10, 15):
        tile_edges = pyogrio.read_dataframe(viewer_dir / 'edges.pmtiles', layer='edges', ZOOM_LEVEL=zoom)
        assert dict(tile_edges[['eid', 'eid2']].drop_duplicates().itertuples(index=False)) == {0: -1, 1: 3, 2: -1}
    for zoom in range(13, 15):
        tile_nodes = pyogrio.read_dataframe(viewer_dir / 'nodes.pmtiles', layer='nodes', ZOOM_LEVEL=zoom)
        assert sorted(tile_nodes['id'].unique()) == [0, 1, 2]


def test_build_viewer_fetches_map_when_not_provided(mocker, config, nodes, edges):
    get_map = mocker.patch('roadgraphtool.export.get_map_from_db', return_value=(nodes, edges))
    viewer.build_viewer(config)
    get_map.assert_called_once_with(config)
    assert (config.viewer.dir / 'graph.bin').exists()


def test_tile_edges():
    a, b, c = (14.40, 50.05), (14.41, 50.06), (14.42, 50.05)
    edges = gpd.GeoDataFrame({
        'u': [0, 1, 1, 2, 0, 0],
        'v': [1, 0, 2, 1, 1, 2],
        'geom': [
            LineString([a, b]),
            LineString([b, a]),  # reverse of 0
            LineString([b, c]),
            LineString([c, (14.415, 50.04), b]),  # 2 -> 1 with a different geometry than 1 -> 2
            LineString([a, b]),  # duplicate of 0 in the same direction, no reverse left for it
            LineString([a, c]),  # one-way
        ],
    }, geometry='geom', crs="EPSG:4326")
    edges['eid'] = edges.index

    features = viewer.tile_edges(edges)

    assert dict(features[['eid', 'eid2']].itertuples(index=False)) == {0: 1, 2: -1, 3: -1, 4: -1, 5: -1}
    assert features.geometry.name == 'geom'
