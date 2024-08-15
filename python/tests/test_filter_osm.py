import os
import pathlib
import pytest
import xml.etree.ElementTree as ET
from scripts.filter_osm import check_strategy, extract_id, load_multipolygon_by_id, extract_bbox, InvalidInputError

def test_check_strategy():
    assert check_strategy("simple") == True
    assert check_strategy("complete_ways") == True
    assert check_strategy("smart") == True
    assert check_strategy("invalid_strategy") == False
    
@pytest.fixture
def expected_multipolygon_id():
    parent_dir = pathlib.Path(__file__).parent
    file_path = str(parent_dir) + "/data/expected_multipolygon_id.osm"
    with open(file_path, 'rb') as f:
        return f.read()

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile", return_value=True)

@pytest.fixture
def mock_open(mocker):
    return mocker.patch("builtins.open", mocker.mock_open())

@pytest.fixture
def mock_remove(mocker):
    return mocker.patch("os.remove")

def test_load_multigon_by_id_url(mocker,expected_multipolygon_id):
    relation_id = 5986438
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"
    # https://www.openstreetmap.org/api/0.6/relation/5986438/full

    # Check HTTP handling
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = expected_multipolygon_id

    result = load_multipolygon_by_id(relation_id)
    mock_get.assert_called_once_with(url)
    assert result == expected_multipolygon_id

def test_load_multigon_by_id_contains_id(mocker, expected_multipolygon_id):
    relation_id = 5986438

    mock_get = mocker.patch('requests.get')
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = expected_multipolygon_id

    result = load_multipolygon_by_id(relation_id)

    # Check if the result contains the relation_id
    tree = ET.ElementTree(ET.fromstring(result))
    root = tree.getroot()
    relation_id_str = str(relation_id)

    contains_relation_id = any(
        relation.attrib.get('id') == relation_id_str
        for relation in root.findall('relation')
    )

    assert contains_relation_id, f"Result does not contain the relation_id {relation_id}"

def test_extract_id_remove_file(mocker, expected_multipolygon_id, mock_open, mock_remove):
    relation_id = 5986438
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    input_file = str(parent_dir) +  "/python/tests/data/id_test.osm"

    mocker.patch("scripts.filter_osm.load_multigon_by_id", return_value=expected_multipolygon_id)
    extract_id(relation_id, input_file)

    # Check that tmp_file was created with expected content
    tmp_file = str(parent_dir) + "/resources/to_extract.osm"
    mock_open.assert_called_once_with(tmp_file, 'wb')
    mock_open().write.assert_called_once_with(expected_multipolygon_id)

    # Check that tmp_file was removed
    mock_remove.assert_called_once_with(tmp_file)
    
def test_extract_id_contains_id():
    relation_id = 5986438
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    input_file = str(parent_dir) + "/python/tests/data/id_test.osm"
    output_file = str(parent_dir) +  "/resources/id_extract.osm"

    extract_id(relation_id, input_file)

    # Check that output file was created
    assert os.path.exists(output_file), "Output file was not created"

    # Check that output file contains relation_id
    with open(output_file, 'rb') as f:
        tree = ET.ElementTree(ET.fromstring(f.read()))
        root = tree.getroot()
        relation_id_str = str(relation_id)

        contains_relation_id = any(
            relation.attrib.get('id') == relation_id_str
            for relation in root.findall('relation')
        )
        assert contains_relation_id, f"File content does not contain the relation_id {relation_id_str}"

    os.remove(output_file)

def test_valid_bbox_coords(mock_subprocess_run):
    coords = "12.3456,78.9012,34.5678,90.1234"
    input_file = "test.osm.pbf"
    extract_bbox(coords, input_file)
    expected_command = [
        "osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"
    ]
    mock_subprocess_run.assert_called_once_with(expected_command)

def test_valid_bbox_config(mock_subprocess_run, mock_os_path_isfile):
    coords = "path/to/config/file.geojson"
    input_file = "test.osm.pbf"
    mock_os_path_isfile.return_value = True
    extract_bbox(coords, input_file)
    expected_command = [
        "osmium", "extract", "-c", coords, input_file]
    mock_subprocess_run.assert_called_once_with(expected_command)


def test_invalid_coords_and_non_existent_file(mock_subprocess_run, mock_os_path_isfile):
    coords = "invalid,coords,string"
    input_file = "test.osm.pbf"
    mock_os_path_isfile.return_value = False
    with pytest.raises(InvalidInputError, match="Invalid coordinates or config file."):
        extract_bbox(coords, input_file)
    mock_subprocess_run.assert_not_called()
