from pathlib import Path

import pytest

from roadgraphtool.db import db
from roadgraphtool.db_operations import (compute_strong_components,
                                         contract_graph_in_area)
from roadgraphtool.insert_area import insert_area
from roadgraphtool.insert_area import read_json_file as read_area
from scripts.install_sql import main as pre_pocessing
from scripts.process_osm import import_osm_to_db

TEST_DATA_PATH = Path(__file__).parent / "data"


def check_setup_of_database():
    query = """SELECT EXISTS (
   SELECT FROM information_schema.tables 
   WHERE  table_schema = 'public'
   AND    table_name   = 'areas'
);"""
    return db.execute_count_query(query)


@pytest.fixture(scope="module")
def setup():
    if not check_setup_of_database():
        pre_pocessing()

    import_osm_to_db(str(TEST_DATA_PATH / "integration_test.osm"))

    insert_area(
        1,
        "Deutschland",
        "test area",
        read_area(str(TEST_DATA_PATH / "integration_area.json")),
    )


def test_integration_contraction(setup):
    contract_graph_in_area(1, 4326, fill_speed=False)

    contracted_nodes = db.execute_sql_and_fetch_all_rows(
        "SELECT id FROM nodes WHERE contracted;"
    )
    assert all(num in [(6,), (7,), (8,)] for num in contracted_nodes)

    edges = db.execute_sql_and_fetch_all_rows('SELECT "from", "to" FROM edges;')

    assert all(
        pair in [(3, 4), (2, 1), (1, 2), (5, 3), (5, 2), (4, 3), (2, 3), (3, 2)]
        for pair in edges
    )


def test_integration_strongly_connected_components(setup):
    compute_strong_components(1)

    component_data = db.execute_sql_and_fetch_all_rows(
        "SELECT component_id, node_id FROM component_data"
    )

    assert all(
        pair in [(0, 1), (0, 2), (0, 3), (0, 4), (1, 5)] for pair in component_data
    )


# The flow is
# install_sql.py - import main as "pre_processing"
# import_osm_to_db, post-processing
# insert_area
# Graph operations:
# - contraction of the graph
# - computing strongly connected components

# QAs:
# Is there a way in our python project to remove everything from db
