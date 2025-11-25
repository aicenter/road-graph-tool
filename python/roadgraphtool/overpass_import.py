
import osmnx as ox
from typing import Dict


def run_overpass_import(config: Dict):
    graph = ox.graph_from_place(config['importer']['area_name'], network_type='drive')