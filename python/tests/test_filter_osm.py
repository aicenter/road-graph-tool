import os
import pathlib
import tempfile
import pytest
import xml.etree.ElementTree as ET

from roadgraphtool.exceptions import InvalidInputError, MissingInputError
from scripts.filter_osm import check_strategy, extract_id, is_valid_extension, load_multipolygon_by_id, extract_bbox, main, RESOURCES_DIR

TESTS_DIR = pathlib.Path(__file__).parent.parent.parent / "python/tests/data"

@pytest.fixture
def expected_multipolygon_id():
    file_path = TESTS_DIR / "expected_multipolygon_id.osm"
    with open(file_path, 'rb') as f:
        return f.read()

@pytest.fixture
def mock_open(mocker):
    return mocker.patch("builtins.open", mocker.mock_open())

# TESTS:

def test_is_valid_extension_valid():
    valid_file = "test.osm"
    assert is_valid_extension(valid_file) == True

def test_is_valid_extension_invalid():
    invalid_file = "test.pdf"
    assert is_valid_extension(invalid_file) == False

def test_check_strategy():
    assert check_strategy("simple") == None
    assert check_strategy("complete_ways") == None
    assert check_strategy("smart") == None
    with pytest.raises(InvalidInputError, match="Invalid strategy type. Call filter_osm.py -h/--help to display help."):
        check_strategy("invalid_strategy")

def test_load_multipolygon_by_id_url(mocker,expected_multipolygon_id):
    relation_id = 5986438
    url = f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full"

    # Check HTTP handling
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = expected_multipolygon_id

    result = load_multipolygon_by_id(relation_id)
    mock_get.assert_called_once_with(url)
    assert result == expected_multipolygon_id

def test_load_multipolygon_by_id_contains_id(mocker, expected_multipolygon_id):
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
    
def test_extract_id_contains_id():
    relation_id = 5986438
    input_file = TESTS_DIR / "id_test.osm"
    output_file = RESOURCES_DIR /  "id_extract.osm"

    extract_id(input_file, relation_id)

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
        assert contains_relation_id, f"File content does not contain the relation_id {relation_id_str}."

    os.remove(output_file)

def test_extract_bbox_valid_coords(mock_subprocess_run):
    coords = "12.3456,78.9012,34.5678,90.1234"
    input_file = "test.osm.pbf"
    extract_bbox(input_file, coords)
    expected_command = [
        "osmium", "extract", "-b", coords, input_file, "-o", "extracted-bbox.osm.pbf"
    ]
    mock_subprocess_run.assert_called_once_with(expected_command)

def test_extract_bbox_config_valid(mock_subprocess_run, mock_os_path_isfile):
    coords = "path/to/config/file.geojson"
    input_file = "test.osm.pbf"
    mock_os_path_isfile.return_value = True
    extract_bbox(input_file, coords)
    expected_command = [
        "osmium", "extract", "-c", coords, input_file]
    mock_subprocess_run.assert_called_once_with(expected_command)

def test_extract_bbox_coords_and_config_invalid(mock_subprocess_run, mock_os_path_isfile):
    coords = "invalid,coords,string"
    input_file = "test.osm.pbf"
    mock_os_path_isfile.return_value = False
    with pytest.raises(InvalidInputError, match="Invalid coordinates or config file."):
        extract_bbox(input_file, coords)
    mock_subprocess_run.assert_not_called()

def test_main_inputfile_invalid():
    arg_list = ["id", "invalid_file.osm"]
    with pytest.raises(FileNotFoundError, match="File 'invalid_file.osm' does not exist."):
        main(arg_list)

def test_main_inputfile_extension_invalid():
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
        arg_list = ["id", tmp_file.name]
        with pytest.raises(InvalidInputError, match="File must have one of the following extensions: osm, osm.pbf, osm.bz2"):
            main(arg_list)

def test_main_id_missing():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["id", tmp_file.name]
        with pytest.raises(MissingInputError, match="Existing relation ID must be specified."):
            main(arg_list)

def test_main_id_invalid_strategy():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["id", tmp_file.name, "-rid", "1234", "-s", "invalid"]
        with pytest.raises(InvalidInputError, match="Invalid strategy type. Call filter_osm.py -h/--help to display help."):
            main(arg_list)

def test_main_id_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["id", tmp_file.name, "-rid", "1234"]
        mock_extract_id = mocker.patch('scripts.filter_osm.extract_id')
        main(arg_list)
        mock_extract_id.assert_called_once_with(arg_list[1], arg_list[3], None)

def test_main_id_startegy_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["id", tmp_file.name, "-rid", "1234", "-s", "simple"]
        mock_extract_id = mocker.patch('scripts.filter_osm.extract_id')
        main(arg_list)
        mock_extract_id.assert_called_once_with(arg_list[1], arg_list[3], "simple")

def test_main_b_missing_coord():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name]
        with pytest.raises(MissingInputError, match="Coordinates or config file need to be specified with the 'b' flag."):
            main(arg_list)

def test_main_b_strategy_invalid():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name, "-c", "10,20,30,40", "-s", "invalid"]
        with pytest.raises(InvalidInputError, match="Invalid strategy type. Call filter_osm.py -h/--help to display help."):
            main(arg_list)

def test_main_b_coords_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name, "-c", "10,20,30,40"]
        mock_extract_bbox = mocker.patch('scripts.filter_osm.extract_bbox')
        main(arg_list)
        mock_extract_bbox.assert_called_once_with(arg_list[1], arg_list[3], None)

def test_main_b_config_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file, tempfile.NamedTemporaryFile(suffix=".json") as config_file:
        arg_list = ["b", tmp_file.name, "-c", config_file.name]
        mock_extract_bbox = mocker.patch('scripts.filter_osm.extract_bbox')
        main(arg_list)
        mock_extract_bbox.assert_called_once_with(arg_list[1], arg_list[3], None)

def test_main_b_strategy_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name, "-c", "10,20,30,40", "-s", "simple"]
        mock_extract_bbox = mocker.patch('scripts.filter_osm.extract_bbox')
        main(arg_list)
        mock_extract_bbox.assert_called_once_with(arg_list[1], arg_list[3], "simple")

def test_main_f_missing():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["f", tmp_file.name]
        with pytest.raises(MissingInputError, match="Expression file needs to be specified."):
            main(arg_list)

def test_main_f_expressionfile_invalid():
    invalid_expression = "invalid_expression.txt"
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["f", tmp_file.name, "-e", invalid_expression]
        with pytest.raises(FileNotFoundError, match=f"File '{invalid_expression}' does not exist."):
            main(arg_list)

def test_main_f_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file, tempfile.NamedTemporaryFile(suffix=".txt") as expression_file:
        arg_list = ["f", tmp_file.name, "-e", expression_file.name]
        mock_run_osmium_filter = mocker.patch('scripts.filter_osm.run_osmium_filter')
        main(arg_list)
        mock_run_osmium_filter.assert_called_once_with(arg_list[1], arg_list[3], False)

def test_main_f_valid_R(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file, tempfile.NamedTemporaryFile(suffix=".txt") as expression_file:
        arg_list = ["f", tmp_file.name, "-e", expression_file.name, "-R"]
        mock_run_osmium_filter = mocker.patch('scripts.filter_osm.run_osmium_filter')
        main(arg_list)
        mock_run_osmium_filter.assert_called_once_with(arg_list[1], arg_list[3], True)