import os
import xml.etree.ElementTree as ET

import pytest
import importlib.resources as resources

from copy import deepcopy

import roadgraphtool.db
from roadgraphtool.exceptions import MissingInputError, InvalidInputError
from roadgraphtool.process_osm import run_osmium_cmd, import_osm_to_db, run_osm2pgsql_cmd, setup_ssh_tunnel, \
    postprocess_osm_import
from roadgraphtool.db import db
from scripts.find_bbox import find_min_max
from tests.conftest import TESTS_DIR, config as default_test_config, test_resources_path


@pytest.fixture
def bounding_box():
    file_path = TESTS_DIR / "bbox_test.osm"
    with open(file_path, 'rb') as f:
        return f.read()


@pytest.fixture
def renumber_test_files():
    input_file = str(TESTS_DIR / "renumber_test.osm")
    output_file = TESTS_DIR / "renumber_test_output.osm"
    return input_file, output_file


@pytest.fixture
def sort_test_files():
    input_file = str(TESTS_DIR / "sort_test.osm")
    output_file = TESTS_DIR / "sort_test_output.osm"
    return input_file, output_file


@pytest.fixture
def mock_run_osm2pgsql_cmd(mocker):
    return mocker.patch('scripts.process_osm.run_osm2pgsql_cmd')


def is_renumbered_by_id(content, obj_type):
    """Function to check if the obj_type IDs are renumbered in ascending order"""
    root = ET.fromstring(content)
    ids = []
    for object in root.findall(obj_type):
        obj_id = int(object.get('id'))
        ids.append(obj_id)

    expected_ids = list(range(1, len(ids) + 1))
    return ids == expected_ids


def is_sorted_by_id(content, obj_type):
    """Function to check if the obj_type IDs are sorted in ascending order"""
    root = ET.fromstring(content)
    ids = []
    for object in root.findall(obj_type):
        obj_id = int(object.get('id'))
        ids.append(obj_id)

    return ids == sorted(ids)


# TESTS:

def test_find_min_max(bounding_box):
    min_lon, min_lat, max_lon, max_lat = find_min_max(bounding_box)
    assert min_lon == 15.0
    assert min_lat == 5.0
    assert max_lon == 30.0
    assert max_lat == 15.0


@pytest.mark.usefixtures("teardown_db")
def test_run_osm2pgsql_cmd(test_schema, test_tables):
    style_file_path = str(TESTS_DIR / "test_default.lua")
    input_file = str(TESTS_DIR / "bbox_test.osm")

    test_config = deepcopy(default_test_config)
    test_config.importer.input_file = input_file
    test_config.importer.style_file = style_file_path
    test_config.importer.schema = test_schema


    run_osm2pgsql_cmd(test_config)

    expected_count = {test_tables[0]: 6, test_tables[1]: 0, test_tables[2]: 1}

    cursor = db.get_new_cursor()
    for table, count in expected_count.items():
        cursor.execute(f'SELECT COUNT(*) FROM {test_schema}.{table};')
        nodes_count = cursor.fetchone()[0]
        assert nodes_count == count

    cursor.execute(f'SELECT * FROM {test_schema}.{test_tables[0]} WHERE node_id=1;')
    node = cursor.fetchone()
    assert node is not None

    cursor.execute(f'SELECT * FROM {test_schema}.{test_tables[0]} WHERE node_id=7;')
    node = cursor.fetchone()
    assert node is None

    cursor.close()


def test_run_osmium_cmd_renumber(renumber_test_files):
    input_file, output_file = renumber_test_files
    run_osmium_cmd('r', input_file, output_file)
    assert os.path.exists(output_file)

    with open(output_file, 'r') as f:
        content = f.read()

    assert is_renumbered_by_id(content, 'node') == True
    assert is_renumbered_by_id(content, 'way') == True
    assert is_renumbered_by_id(content, 'relation') == True

    os.remove(output_file)


def test_run_osmium_cmd_sort(sort_test_files):
    input_file, output_file = sort_test_files
    run_osmium_cmd('s', input_file, output_file)
    assert os.path.exists(output_file)

    with open(output_file, 'r') as f:
        content = f.read()
    assert is_sorted_by_id(content, 'node') == True
    assert is_sorted_by_id(content, 'way') == True
    assert is_sorted_by_id(content, 'relation') == True

    os.remove(output_file)
