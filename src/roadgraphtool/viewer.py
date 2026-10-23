import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np

import roadgraphtool.export
from roadgraphtool.overpass_client import _read_nested

STATIC_DIR = Path(__file__).resolve().parent / "resources" / "viewer"

# the viewer shows the nodes only from this zoom (see viewer.js), so there is no point in generating them for lower zooms
NODES_MIN_ZOOM = 13


def _write_tiles(gdf: gpd.GeoDataFrame, path: Path, layer: str, min_zoom: int, max_zoom: int):
    logging.info("Writing %d features of layer '%s' to %s (zoom %d-%d)", len(gdf), layer, path, min_zoom, max_zoom)
    path.unlink(missing_ok=True)
    gdf.to_file(path, driver="PMTiles", layer=layer, engine="pyogrio", MINZOOM=min_zoom, MAXZOOM=max_zoom)


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
    node_ids = nodes["id"].to_numpy()
    db_ids = np.empty(node_count, dtype="<f8")
    db_ids[node_ids] = nodes["db_id"].to_numpy()
    coords = np.empty((node_count, 2), dtype="<f4")
    coords[node_ids] = np.column_stack((nodes.geometry.x, nodes.geometry.y))

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

    if nodes is None or edges is None:
        nodes, edges = roadgraphtool.export.get_map_from_db(config)

    nodes = nodes.to_crs(4326)
    edges = edges.to_crs(4326).reset_index(drop=True)
    edges["eid"] = edges.index
    edges["length"] = edges["length"].round(1)

    viewer_dir.mkdir(parents=True, exist_ok=True)
    # the other attributes are in the routing graph, so the tiles stay small
    _write_tiles(edges[["eid", edges.geometry.name]], viewer_dir / "edges.pmtiles", "edges", min_zoom, max_zoom)
    _write_tiles(
        nodes[["id", nodes.geometry.name]], viewer_dir / "nodes.pmtiles", "nodes", max(min_zoom, NODES_MIN_ZOOM), max_zoom
    )
    write_graph(nodes, edges, viewer_dir / "graph.bin")

    min_lon, min_lat, max_lon, max_lat = edges.total_bounds
    build_info = {
        "build_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "title": title,
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
    with open(viewer_dir / "build.json", "w", encoding="utf-8") as file:
        json.dump(build_info, file, indent=2)

    for static_file in STATIC_DIR.iterdir():
        shutil.copy2(static_file, viewer_dir / static_file.name)

    logging.info("Viewer saved to %s", viewer_dir.absolute())
