import os
import xml.etree.ElementTree as ET
from pathlib import Path

from roadgraphtool.db import db
from roadgraphtool.db_operations import (compute_strong_components,
                                         contract_graph_in_area)
from roadgraphtool.insert_area import insert_area
from roadgraphtool.insert_area import read_json_file as read_area
from roadgraphtool.map import get_map as export_nodes_edges
from scripts.install_sql import main as pre_pocessing
from scripts.process_osm import import_osm_to_db

TEST_DATA_PATH = Path(__file__).parent / "data"

# Helper functions


def check_setup_of_database():
    query = """SELECT EXISTS (
   SELECT FROM information_schema.tables 
   WHERE  table_schema = 'public'
   AND    table_name   = 'areas'
);"""
    return db.execute_count_query(query)


def parse_osm_file(file_path):
    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Initialize the dictionary to store the OSM data
    osm_data = {"nodes": {}, "ways": {}}

    # Parse nodes
    for node in root.findall("node"):
        node_id = node.get("id")
        node_data = {
            "id": node_id,
            "lat": node.get("lat"),
            "lon": node.get("lon"),
            "version": node.get("version"),
            "timestamp": node.get("timestamp"),
            "uid": node.get("uid"),
            "user": node.get("user"),
            "tags": {},
        }

        # Parse tags for nodes
        for tag in node.findall("tag"):
            node_data["tags"][tag.get("k")] = tag.get("v")

        osm_data["nodes"][node_id] = node_data

    # Parse ways
    for way in root.findall("way"):
        way_id = way.get("id")
        way_data = {
            "id": way_id,
            "version": way.get("version"),
            "timestamp": way.get("timestamp"),
            "uid": way.get("uid"),
            "user": way.get("user"),
            "nodes": [],
            "tags": {},
        }

        # Parse node references for ways
        for nd in way.findall("nd"):
            way_data["nodes"].append(nd.get("ref"))

        # Parse tags for ways
        for tag in way.findall("tag"):
            way_data["tags"][tag.get("k")] = tag.get("v")

        osm_data["ways"][way_id] = way_data

    return osm_data


# Testing functions


def test_integration_base_flow():
    """
    Integration test:
        Base flow:
            1) Import test data:
                i) set up basic tables (optionally)
                ii) import osm file
                iii) add test area
            2) Execute contraction of graph in the area
            3) Execute computation of strong components in the area
            4) Export data to files
            5) Destroy testing environment
    """

    # 1) setting up the database with needed information
    if not check_setup_of_database():
        pre_pocessing()

    # change the main schema
    db.execute_sql("CALL test_env_constructor();")

    import_osm_to_db(str(TEST_DATA_PATH / "integration_test.osm"), schema="test_env")

    insert_area(
        1,
        "Deutschland",
        "test area",
        read_area(str(TEST_DATA_PATH / "integration_area.json")),
    )

    # read osm file to dictionary
    osm_dict = parse_osm_file(TEST_DATA_PATH / "integration_test.osm")
    print(osm_dict)

    # Test that importing osm data and area was done successfully
    nodes = db.execute_sql_and_fetch_all_rows(
        "SELECT id, ST_X(geom), ST_Y(geom) FROM nodes;"
    )
    nodes_set = set(nodes)

    expected_nodes = osm_dict["nodes"]
    expected_nodes_set = set(
        [
            (int(key), float(value["lon"]), float(value["lat"]))
            for key, value in expected_nodes.items()
        ]
    )

    assert nodes_set == expected_nodes_set

    ways = db.execute_sql_and_fetch_all_rows(
        'SELECT id, tags, "from", "to", oneway FROM ways;'
    )

    ways_set = set(
        [
            (way[0], str(dict(sorted(way[1].items()))), way[2], way[3], way[4])
            for way in ways
        ]
    )

    expected_ways = osm_dict["ways"]
    expected_ways_set = set(
        [
            (
                int(key),
                str(
                    {
                        k: v for k, v in value["tags"].items() if k != "oneway"
                    }  # the same tags, but without "oneway" tag
                ),
                int(value["nodes"][0]),
                int(value["nodes"][-1]),
                value["tags"]["oneway"] == "yes",
            )
            for key, value in expected_ways.items()
        ]
    )

    assert expected_ways_set == ways_set

    nodes_ways = db.execute_sql_and_fetch_all_rows(
        "SELECT way_id, node_id FROM nodes_ways;"
    )
    nodes_ways_set = set(nodes_ways)

    expected_nodes_ways = set()
    for way_id, way in expected_ways.items():
        for node_id in way["nodes"]:
            expected_nodes_ways.add((int(way_id), int(node_id)))

    assert nodes_ways_set == expected_nodes_ways

    area = db.execute_sql_and_fetch_all_rows(
        "SELECT id, name, description FROM areas;"
    )[0]

    expected_area = (1, "Deutschland", "test area")

    assert area == expected_area

    # 2) Call contraction
    contract_graph_in_area(1, 4326, fill_speed=False)

    # GET updated data from db and assert
    contracted_nodes = db.execute_sql_and_fetch_all_rows(
        "SELECT id FROM nodes WHERE contracted;"
    )
    assert set([(6,), (7,), (8,)]) == set(contracted_nodes)

    edges = db.execute_sql_and_fetch_all_rows('SELECT "from", "to" FROM edges;')

    assert set([(3, 4), (2, 1), (1, 2), (5, 3), (5, 2), (4, 3), (2, 3), (3, 2)]) == set(
        edges
    )

    # 3) Call Compute Strong Components
    compute_strong_components(1)

    # GET updated data from db and assert
    component_data = db.execute_sql_and_fetch_all_rows(
        "SELECT component_id, node_id FROM component_data"
    )

    assert set([(0, 1), (0, 2), (0, 3), (0, 4), (1, 5)]) == set(component_data)

    # 4) Export data to files
    TMP_DIR = Path(__file__).parent / "TMP"
    os.mkdir(str(TMP_DIR))
    map_path = TMP_DIR / "map"
    area_dir = TMP_DIR / "area_dir"
    os.mkdir(str(map_path))
    os.mkdir(str(area_dir))

    config = {
        "map": {
            "path": str(map_path),
            "SRID_plane": 4326,
        },
        "area_dir": str(area_dir),
        "area": "Deutschland",
        "area_id": 1,
    }
    _ = export_nodes_edges(config)
    assert False

    # 5) Environment destruction
    # test environment desctructor
    db.execute_sql("CALL test_env_destructor();")
