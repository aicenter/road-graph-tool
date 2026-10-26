import json
import logging
import multiprocessing
import os
import shutil
import tempfile
from concurrent.futures import FIRST_EXCEPTION, ProcessPoolExecutor, wait
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from typing import BinaryIO, Callable, Optional

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pmtiles.reader
import pmtiles.tile
import pmtiles.writer
import pyarrow as pa
import pyogrio
import shapely
from tqdm import tqdm

import roadgraphtool.export
from roadgraphtool.overpass_client import _read_nested

STATIC_DIR = Path(__file__).resolve().parent / "resources" / "viewer"

# the viewer shows the nodes only from this zoom (see viewer.js), so there is no point in generating them for lower zooms
NODES_MIN_ZOOM = 13

# number of features passed to GDAL at once when writing the tiles, i.e., the granularity of the progress bar
TILES_BATCH_SIZE = 10_000


@dataclass
class TileLayer:
    features: gpd.GeoDataFrame
    path: Path
    name: str
    min_zoom: int
    max_zoom: int


# number of features processed by a worker of _write_tiles, shared by all workers
_progress: Optional[Synchronized] = None


def _init_tiling_worker(progress: Synchronized):
    global _progress
    _progress = progress


def _write_zoom_level_tiles(
    features_path: Path, path: Path, layer: str, geometry_name: str, geometry_type: str, crs: str, zoom: int
):
    """Runs in a worker process of _write_tiles: writes the tiles of one zoom level with the GDAL PMTiles driver."""
    with pa.OSFile(str(features_path)) as source:
        table = pa.ipc.open_file(source).read_all()

    def batches():
        for batch in table.to_batches(max_chunksize=TILES_BATCH_SIZE):
            yield batch
            # GDAL asks for the next batch after it processed this one
            with _progress.get_lock():
                _progress.value += batch.num_rows

    pyogrio.write_arrow(
        pa.RecordBatchReader.from_batches(table.schema, batches()),
        path,
        layer=layer,
        driver="PMTiles",
        geometry_name=geometry_name,
        geometry_type=geometry_type,
        crs=crs,
        MINZOOM=zoom,
        MAXZOOM=zoom,
    )


def _file_source(file: BinaryIO) -> Callable[[int, int], bytes]:
    """PMTiles source reading from an open file (the memory-mapped source of pmtiles keeps the file locked on Windows)."""
    def get_bytes(offset: int, length: int) -> bytes:
        file.seek(offset)
        return file.read(length)

    return get_bytes


def _merge_zoom_levels(parts: list[Path], path: Path):
    """Merges PMTiles files with disjoint zoom levels, ordered by the zoom level, into one file."""
    with ExitStack() as stack:
        sources = [_file_source(stack.enter_context(open(part, "rb"))) for part in parts]
        header = pmtiles.reader.Reader(sources[0]).header()
        metadata = pmtiles.reader.Reader(sources[0]).metadata()
        min_zoom = header["min_zoom"]
        max_zoom = pmtiles.reader.Reader(sources[-1]).header()["max_zoom"]
        for vector_layer in metadata.get("vector_layers", []):
            vector_layer["minzoom"] = min_zoom
            vector_layer["maxzoom"] = max_zoom

        with open(path, "wb") as output:
            writer = pmtiles.writer.Writer(output)
            # tile ids grow with the zoom level, so the merged tiles stay ordered (clustered)
            for source in sources:
                for (z, x, y), data in pmtiles.reader.all_tiles(source):
                    writer.write_tile(pmtiles.tile.zxy_to_tileid(z, x, y), data)
            writer.finalize(header, metadata)


def _write_tiles(layers: list[TileLayer], processes: int):
    """
    Writes each layer to a PMTiles file with the GDAL PMTiles driver.

    GDAL spends most of the time cutting each feature into the tiles of every zoom level, so each zoom level of each
    layer is written by a separate worker process and the zoom levels of a layer are merged into one file afterward.
    The features are streamed to GDAL in batches to report the progress.

    All files are created in a local temporary directory (GDAL builds the tiles in a temporary database next to the
    output file) and the merged files are moved to their paths afterward, because the output directory can be slow
    for random access (e.g., a synced cloud drive).
    """
    with tempfile.TemporaryDirectory() as temporary_dir:
        temporary_dir = Path(temporary_dir)
        tasks = []
        for layer in layers:
            logging.info(
                "Tiling %d features of layer '%s' (zoom %d-%d)", len(layer.features), layer.name, layer.min_zoom,
                layer.max_zoom
            )
            features = layer.features
            table = pa.table(features.to_arrow(geometry_encoding="WKB"))
            features_path = temporary_dir / f"{layer.name}.arrow"
            with pa.OSFile(str(features_path), "wb") as sink, pa.ipc.new_file(sink, table.schema) as file_writer:
                file_writer.write_table(table)
            geometry_types = features.geom_type.unique()
            geometry_type = geometry_types[0] if len(geometry_types) == 1 else "Unknown"
            for zoom in range(layer.min_zoom, layer.max_zoom + 1):
                tasks.append(
                    (features_path, temporary_dir / f"{layer.name}_{zoom}.pmtiles", layer.name, features.geometry.name,
                     geometry_type, features.crs.to_string(), zoom)
                )

        total = sum(len(layer.features) * (layer.max_zoom - layer.min_zoom + 1) for layer in layers)
        progress_value = multiprocessing.Value("q", 0)
        logging.info("Tiling %d zoom levels in %d processes", len(tasks), processes)
        with (
            ProcessPoolExecutor(processes, initializer=_init_tiling_worker, initargs=(progress_value,)) as pool,
            tqdm(total=total, desc="Tiling (features x zoom levels)") as progress,
        ):
            futures = [pool.submit(_write_zoom_level_tiles, *task) for task in tasks]
            try:
                while True:
                    done, not_done = wait(futures, timeout=0.5, return_when=FIRST_EXCEPTION)
                    progress.update(progress_value.value - progress.n)
                    for future in done:
                        future.result()
                    if not not_done:
                        break
            except BaseException:
                pool.shutdown(cancel_futures=True)
                raise

        for layer in layers:
            logging.info("Merging the zoom levels of layer '%s' to %s", layer.name, layer.path)
            parts = [temporary_dir / f"{layer.name}_{zoom}.pmtiles" for zoom in range(layer.min_zoom, layer.max_zoom + 1)]
            merged_path = temporary_dir / f"{layer.name}.pmtiles"
            _merge_zoom_levels(parts, merged_path)
            layer.path.unlink(missing_ok=True)
            shutil.move(merged_path, layer.path)


def tile_edges(edges: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Returns the edge features for the tiles: one feature per edge with its id in ``eid``, except for two-way edges.
    An edge u -> v and an edge v -> u with the same geometry are one feature with the ids ``eid`` and ``eid2``, which
    halves the features of a network with mostly two-way edges. ``eid2`` is -1 for the other features.
    :param edges: edges with columns ``eid`` (equal to the index), ``u``, and ``v``
    """
    keys = pd.DataFrame({
        "eid": edges["eid"].to_numpy(),
        "a": np.minimum(edges["u"], edges["v"]),
        "b": np.maximum(edges["u"], edges["v"]),
        # the normalized geometry is the same for both directions
        "shape": shapely.to_wkb(shapely.normalize(edges.geometry.to_numpy())),
    })
    key_columns = ["a", "b", "shape"]
    forward = keys[edges["u"] < edges["v"]].drop_duplicates(key_columns)
    backward = keys[edges["u"] > edges["v"]].drop_duplicates(key_columns)
    pairs = forward.merge(backward, on=key_columns, suffixes=("", "2"))

    features = edges[["eid", edges.geometry.name]].copy()
    features["eid2"] = -1
    features.loc[pairs["eid"].to_numpy(), "eid2"] = pairs["eid2"].to_numpy()
    features = features.drop(index=pairs["eid2"].to_numpy())
    logging.info("%d edges, %d of them two-way pairs, %d tile features", len(edges), 2 * len(pairs), len(features))
    return features


def _node_coordinates(nodes: gpd.GeoDataFrame) -> np.ndarray:
    """Returns the (lon, lat) coordinates of the nodes indexed by the node id."""
    coords = np.empty((len(nodes), 2))
    coords[nodes["id"].to_numpy()] = np.column_stack((nodes.geometry.x, nodes.geometry.y))
    return coords


def _join_parts(geometries: np.ndarray, eids: np.ndarray) -> np.ndarray:
    """
    Joins the parts of the multi-part edge geometries into one line each.

    The parts of an edge geometry in the database are not ordered along the edge and may go in either direction, so
    concatenating them would produce a zigzag line. Most geometries are joined by ``shapely.line_merge``, which stops
    where the line touches itself and returns an empty geometry for zero-length parts. The remaining ones are joined by
    an Eulerian trail over their parts.
    :param geometries: edge geometries
    :param eids: edge ids of the geometries, for the error message
    :return: one LineString per geometry
    """
    lines = geometries.copy()
    multi_part = shapely.get_type_id(geometries) == shapely.GeometryType.MULTILINESTRING
    lines[multi_part] = shapely.line_merge(geometries[multi_part])
    for index in np.flatnonzero(shapely.get_type_id(lines) != shapely.GeometryType.LINESTRING):
        graph = nx.MultiGraph()
        for part in geometries[index].geoms:
            coords = list(part.coords)
            graph.add_edge(coords[0], coords[-1], coords=coords)
        if not nx.has_eulerian_path(graph):
            raise ValueError(f"The parts of the geometry of the edge {eids[index]} do not form one continuous line")
        coords = []
        for start, end, key in nx.eulerian_path(graph, keys=True):
            part_coords = graph.edges[start, end, key]["coords"]
            if part_coords[0] != start:
                part_coords = part_coords[::-1]
            coords.extend(part_coords if not coords else part_coords[1:])
        lines[index] = shapely.LineString(coords)
    return lines


def write_shapes(features: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, path: Path) -> int:
    """
    Saves the shapes of the edges, used by the viewer to snap the route points to the nearest point on an edge, as a
    little-endian binary file with one shape per edge feature of the tiles (see ``tile_edges``):

    - Int32[f]: id of the edge in the direction of the shape (``eid``)
    - Int32[f]: id of the reverse edge (``eid2``), -1 for one-way edges
    - Uint32[f + 1]: offsets of the vertices of each shape
    - Float32[2V]: vertex coordinates (lon, lat)

    Each shape is one line going from the node ``u`` to the node ``v`` of the edge ``eid``: the parts of multi-part
    geometries are joined into one line (see ``_join_parts``) and the lines stored in the opposite direction are
    reversed.
    :param features: edge features from ``tile_edges``
    :param nodes: nodes with ids 0..n-1 in the column ``id`` and geometry in EPSG:4326
    :param edges: edges with columns ``u`` and ``v`` indexed by ``eid``
    :return: number of vertices
    """
    eids = features["eid"].to_numpy()
    lines = _join_parts(features.geometry.to_numpy(), eids)
    coords, shape_of_vertex = shapely.get_coordinates(lines, return_index=True)
    counts = np.bincount(shape_of_vertex, minlength=len(features))
    offsets = np.zeros(len(features) + 1, dtype="<u4")
    offsets[1:] = np.cumsum(counts)

    node_coords = _node_coordinates(nodes)
    u_coords = node_coords[edges["u"].to_numpy()[eids]]
    v_coords = node_coords[edges["v"].to_numpy()[eids]]
    first = coords[offsets[:-1]]
    last = coords[offsets[1:] - 1]
    distance = lambda a, b: np.linalg.norm(a - b, axis=1)
    reverse = distance(first, v_coords) + distance(last, u_coords) < distance(first, u_coords) + distance(last, v_coords)
    position_in_shape = np.arange(len(coords)) - offsets[shape_of_vertex]
    position_in_shape = np.where(
        reverse[shape_of_vertex], counts[shape_of_vertex] - 1 - position_in_shape, position_in_shape
    )
    coords = coords[offsets[shape_of_vertex] + position_in_shape]

    logging.info("Saving %d edge shapes with %d vertices to %s", len(features), len(coords), path)
    with open(path, "wb") as file:
        file.write(eids.astype("<i4").tobytes())
        file.write(features["eid2"].to_numpy().astype("<i4").tobytes())
        file.write(offsets.tobytes())
        file.write(coords.astype("<f4").tobytes())
    return len(coords)


def write_graph(nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, path: Path):
    """
    Saves the graph for the routing in the viewer as a little-endian binary file in the CSR format:

    - Float64[n]: node database ids (``db_id``), indexed by the node id
    - Float32[2n]: node coordinates (lon, lat), indexed by the node id
    - Uint32[n + 1]: offsets of the outgoing edges of each node
    - Uint32[m]: target node of each edge
    - Float32[m]: length of each edge in meters
    - Uint32[m]: id of each edge (``eid``, the id of the edge feature in the tiles)

    :param nodes: nodes with ids 0..n-1 in the column ``id``, columns ``db_id``, and geometry in EPSG:4326
    :param edges: edges with columns ``eid``, ``u``, ``v``, and ``length``
    """
    node_count = len(nodes)
    db_ids = np.empty(node_count, dtype="<f8")
    db_ids[nodes["id"].to_numpy()] = nodes["db_id"].to_numpy()
    coords = _node_coordinates(nodes).astype("<f4")

    order = np.argsort(edges["u"].to_numpy(), kind="stable")
    u = edges["u"].to_numpy()[order]
    offsets = np.zeros(node_count + 1, dtype="<u4")
    offsets[1:] = np.cumsum(np.bincount(u, minlength=node_count))

    logging.info("Saving the routing graph to %s", path)
    with open(path, "wb") as file:
        file.write(db_ids.tobytes())
        file.write(coords.tobytes())
        file.write(offsets.tobytes())
        file.write(edges["v"].to_numpy()[order].astype("<u4").tobytes())
        file.write(edges["length"].to_numpy()[order].astype("<f4").tobytes())
        file.write(edges["eid"].to_numpy()[order].astype("<u4").tobytes())


def build_viewer(config, nodes: Optional[gpd.GeoDataFrame] = None, edges: Optional[gpd.GeoDataFrame] = None):
    """
    Exports the road network of the configured area to a static web viewer (vector tiles, routing graph, and the
    HTML/JS files) in ``viewer.dir``. The directory can be uploaded to any static web hosting as it is.
    :param config: instance configuration
    :param nodes: nodes from the export step, fetched from the database if not provided
    :param edges: edges from the export step, fetched from the database if not provided
    """
    viewer_dir = Path(config.viewer.dir)
    min_zoom = _read_nested(config, "viewer.min_zoom", 10)
    max_zoom = _read_nested(config, "viewer.max_zoom", 16)
    title = _read_nested(config, "viewer.title", "Road network")
    processes = _read_nested(config, "viewer.processes", os.cpu_count())

    if nodes is None or edges is None:
        nodes, edges = roadgraphtool.export.get_map_from_db(config)

    nodes = nodes.to_crs(4326)
    edges = edges.to_crs(4326).reset_index(drop=True)
    edges["eid"] = edges.index
    edges["length"] = edges["length"].round(1)

    viewer_dir.mkdir(parents=True, exist_ok=True)
    edge_features = tile_edges(edges)
    # the other attributes are in the routing graph, so the tiles stay small
    _write_tiles([
        TileLayer(edge_features, viewer_dir / "edges.pmtiles", "edges", min_zoom, max_zoom),
        TileLayer(
            nodes[["id", nodes.geometry.name]], viewer_dir / "nodes.pmtiles", "nodes", max(min_zoom, NODES_MIN_ZOOM),
            max_zoom
        ),
    ], processes)
    write_graph(nodes, edges, viewer_dir / "graph.bin")
    vertex_count = write_shapes(edge_features, nodes, edges, viewer_dir / "shapes.bin")

    min_lon, min_lat, max_lon, max_lat = edges.total_bounds
    build_info = {
        "build_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "title": title,
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "shape_count": len(edge_features),
        "vertex_count": vertex_count,
    }
    with open(viewer_dir / "build.json", "w", encoding="utf-8") as file:
        json.dump(build_info, file, indent=2)

    for static_file in STATIC_DIR.iterdir():
        shutil.copy2(static_file, viewer_dir / static_file.name)

    logging.info("Viewer saved to %s", viewer_dir.absolute())
