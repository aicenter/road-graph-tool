import os
import pathlib
import pytest
import requests
import xml.etree.ElementTree as ET
import tempfile
import json
from scripts.filter_osm import check_strategy, extract_id, load_multigon_by_id, extract_bbox_osmium, InvalidInputError

def test_check_strategy():
    assert check_strategy("simple") == True
    assert check_strategy("complete_ways") == True
    assert check_strategy("smart") == True
    assert check_strategy("invalid_strategy") == False
    
@pytest.fixture
def expected_multipolygon_id():
    # Path to the file containing expected content
    parent_dir = pathlib.Path(__file__).parent.parent
    file_path = str(parent_dir) + "/tests/data/expected_multipolygon_id.osm"
    with open(file_path, 'rb') as f:
        return f.read()

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")

@pytest.fixture
def mock_open(mocker):
    return mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps({
        "extracts": [
            {
                "output": "resources/extracted-bbox.osm.pbf",
                "bbox": [25.12, 54.57, 25.43, 54.75]
            }
        ]
    })))

@pytest.fixture
def setup_geojson_config(expected_multipolygon_id):
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    path_geojson = parent_dir / "resources" / "extract-id.geojson"
    path_tmp_file = parent_dir / "resources" / "to_extract.osm"
    path_output_file = parent_dir / "resources" / "id_extract.osm"

    geojson_content = {
        "extracts": [
            {
                "output": str(path_output_file.relative_to(parent_dir)),
                "multipolygon": {
                    "file_name": str(path_tmp_file.relative_to(parent_dir)),
                    "file_type": "osm"
                }
            }
        ]
    }
    
    # Ensure directories exist
    path_geojson.parent.mkdir(parents=True, exist_ok=True)
    path_tmp_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the geojson file
    with open(path_geojson, 'w') as f:
        json.dump(geojson_content, f, indent=4)
    
    # Write the temporary file with mock content
    with open(path_tmp_file, 'wb') as f:
        f.write(expected_multipolygon_id)

    # Clean up: Remove the output file if it already exists
    if path_output_file.exists():
        path_output_file.unlink()
    
    return path_geojson, path_output_file


def test_load_multigon_by_id_url(mocker,expected_multipolygon_id):
    relation_id = 5986438
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    # https://www.openstreetmap.org/api/0.6/relation/5986438/full

    # Check HTTP handling
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = expected_multipolygon_id

    result = load_multigon_by_id(relation_id)
    mock_get.assert_called_once_with(url)
    assert result == expected_multipolygon_id

def test_load_multigon_by_id_contains_id(mocker,expected_multipolygon_id):
    relation_id = 5986438

    mock_get = mocker.patch('requests.get')
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = expected_multipolygon_id

    result = load_multigon_by_id(relation_id)

    # Check if the result contains the relation_id
    tree = ET.ElementTree(ET.fromstring(result))
    root = tree.getroot()
    relation_id_str = str(relation_id)

    contains_relation_id = any(
        relation.attrib.get('id') == relation_id_str
        for relation in root.findall('relation')
    )

    assert contains_relation_id, f"Result does not contain the relation_id {relation_id}"

def test_extract_id_remove_file(mocker):
    relation_id = 5986438
    input_file = "tests/data/park.osm"
    
    # Test that tmp_file is not in folder
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    tmp_file = str(parent_dir) + "/resources/to_extract.osm"
    mock_remove = mocker.patch("os.remove")
    mocker.patch("os.path.isfile", return_value=False)
    
    extract_id(relation_id, input_file)
    mock_remove.assert_called_once_with(tmp_file)
    assert not os.path.isfile(tmp_file)

# TODO: finish it
def test_extract_id_contains_id(mocker, expected_multipolygon_id, setup_geojson_config):
    relation_id = 5986438
    path_geojson, path_output_file = setup_geojson_config

    mocker.patch('scripts.filter_osm.load_multigon_by_id', return_value=expected_multipolygon_id)
    mock_subprocess = mocker.patch('subprocess.run')

    parent_dir = pathlib.Path(__file__).parent.parent
    input_file = str(parent_dir) + "/tests/data/park.osm"

    assert os.path.exists(input_file), "Input file does not exist"

    try:
        extract_id(relation_id, input_file)

        mock_subprocess.assert_called_once_with(["osmium", "extract", "-c", str(path_geojson), input_file])
        
        assert os.path.exists(path_output_file), "Output file was not created"

        # # Parse XML content from the file
        # tree = ET.ElementTree(ET.fromstring(file_content))
        # root = tree.getroot()
        # relation_id_str = str(5986438)  # Convert the relation ID to string

        # contains_relation_id = any(
        #     relation.attrib.get('id') == relation_id_str
        #     for relation in root.findall('relation')
        # )
        
        # assert contains_relation_id, f"File content does not contain the relation_id {relation_id_str}"

    finally:
        # Clean up the temporary file
        if os.path.exists(path_output_file):
            os.remove(path_output_file)

def test_valid_bbox_coords(mock_subprocess_run):
    coords = "12.3456,78.9012,34.5678,90.1234"
    input_file = "test.osm.pbf"
    extract_bbox_osmium(coords, input_file)
    expected_command = [
        "osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"
    ]
    mock_subprocess_run.assert_called_once_with(expected_command)

def test_valid_bbox_config(mock_subprocess_run, mock_os_path_isfile, mock_open):
    coords = "path/to/config/file.geojson"
    input_file = "test.osm.pbf"
    mock_os_path_isfile.return_value = True
    extract_bbox_osmium(coords, input_file)
    expected_command = [
        "osmium", "extract", "-c", coords, input_file]
    mock_subprocess_run.assert_called_once_with(expected_command)


def test_invalid_coords_and_non_existent_file(mock_subprocess_run, mock_os_path_isfile):
    coords = "invalid,coords,string"
    input_file = "test.osm.pbf"
    mock_os_path_isfile.return_value = False
    with pytest.raises(InvalidInputError, match="Invalid coordinates or config file."):
        extract_bbox_osmium(coords, input_file)
    mock_subprocess_run.assert_not_called()

# TODO: test_tags_filter