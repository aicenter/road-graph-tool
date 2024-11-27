import pytest
import subprocess
import os
import xml.etree.ElementTree as ET

from roadgraphtool.schema import get_connection
from elevation.add_elevation import *
from tests.test_filter_osm import TESTS_DIR

@pytest.fixture(scope="module")
def test_tables_elevation():
    return 'nodes', 'elevations'

@pytest.fixture
def mock_coords():
    return np.array([
        (1, 45.0, -93.0),
        (2, 46.0, -94.0),
        (3, 47.0, -95.0)], dtype=object)

@pytest.fixture
def mock_json_coords():
    return {'locations': [
        {'lat': 45.0, 'lon': -93.0},
        {'lat': 46.0, 'lon': -94.0},
        {'lat': 47.0, 'lon': -95.0}]}

@pytest.fixture
def mock_elevation():
    return {'locations': [
            {'lat': 45.0, 'lon': -93.0, 'ele': 200},
            {'lat': 46.0, 'lon': -94.0, 'ele': 210},
            {'lat': 47.0, 'lon': -95.0, 'ele': 220}]}

# TESTS:

@pytest.mark.usefixtures("setup_test_schema")
def test_load_coords(test_schema, test_tables_elevation):
    coords = load_coords(test_tables_elevation[0], test_schema)

    assert len(coords) > 0
    assert isinstance(coords, np.ndarray)
    assert coords.shape == (3, 3)

def test_prepare_coords(mock_coords, mock_json_coords):
    # Test that the function returns a list of coordinates
    json_chunk = prepare_coords(mock_coords)

    assert json_chunk == mock_json_coords

def test_get_elevation(mock_json_coords):
    # Test that the function adds elevations to the coordinates
    updated_json_chunk = get_elevation(mock_json_coords)

    assert 'ele' in updated_json_chunk['locations'][0]

def test_save_chunk_to_csv(mock_coords, mock_elevation):
    # Test that the function saves the chunk to a csv file
    file_path = TESTS_DIR / "test_elevation.csv"
    save_chunk_to_csv(file_path, mock_coords, mock_elevation)
    
    assert os.path.exists(file_path)

    with open(file_path, 'r') as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)

    # check headers
    assert rows[0] == ['node_id', 'ele']

    expected = [
        ['1', '200'],
        ['2', '210'],
        ['3', '220']
    ]
    assert rows[1:] == expected
    
    # clean up
    os.remove(file_path)

@pytest.mark.usefixtures("setup_test_schema")
def test_setup_database(test_schema, test_tables_elevation):
    table_query = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = '{test_schema}' 
        AND table_name = '{test_tables_elevation[1]}'
    );
    """
    column_query = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = '{test_schema}' 
        AND table_name = '{test_tables_elevation[0]}' 
        AND column_name = 'elevation'
    );
    """
    setup_database(test_tables_elevation[0], test_tables_elevation[1], test_schema)

    with get_connection() as conn:
        with conn.cursor() as cur:
                cur.execute(table_query)
                table_exists = cur.fetchone()[0]
                cur.execute(column_query)
                column_exists = cur.fetchone()[0]
        conn.commit()
    assert table_exists == True
    assert column_exists == True

@pytest.mark.usefixtures("setup_test_schema")
def test_copy_csv_to_postgres(test_schema, test_tables_elevation):
    setup_database(test_tables_elevation[0], test_tables_elevation[1], test_schema)
    copy_csv_to_postgres(test_schema, test_tables_elevation[1], TESTS_DIR / "temp_ele.csv")

    expected_count = 3
    count_query = f'SELECT COUNT(*) FROM {test_schema}.{test_tables_elevation[1]};'

    with get_connection() as conn:
        with conn.cursor() as cur:
                cur.execute(count_query)
                count = cur.fetchone()[0]
        conn.commit()
    assert count == expected_count

@pytest.mark.usefixtures("setup_test_schema")
def test_update_and_drop_table(test_schema, test_tables_elevation, mock_coords):
    # Test that the function updates the table and drops the old table
    # check that elevation node is empty before updating
    setup_database(test_tables_elevation[0], test_tables_elevation[1], test_schema)

    empty_column_query = f"""
    SELECT COUNT(elevation) from {test_schema}.{test_tables_elevation[0]};
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
                cur.execute(empty_column_query)
                count = cur.fetchone()[0]
        conn.commit()
    assert count == 0

    
    copy_csv_to_postgres(test_schema, test_tables_elevation[1], TESTS_DIR / "temp_ele.csv")
    update_and_drop_table(test_tables_elevation[0], test_tables_elevation[1], test_schema, mock_coords)

    # check that the old table is dropped
    table_query = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = '{test_schema}' 
        AND table_name = '{test_tables_elevation[1]}'
    );
    """
    column_count_query = f"""
    SELECT COUNT(elevation) from {test_schema}.{test_tables_elevation[0]};
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
                cur.execute(table_query)
                table_exists = cur.fetchone()[0]
                cur.execute(column_count_query)
                count = cur.fetchone()[0]
        conn.commit()
    assert table_exists == False
    assert count == 3
