import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pytest
import importlib.resources as resources

from copy import deepcopy

from roadgraphtool.exceptions import MissingInputError, InvalidInputError
from roadgraphtool.process_osm import run_osmium_cmd, main, import_osm_to_db, run_osm2pgsql_cmd, setup_ssh_tunnel, \
    postprocess_osm_import, SQL_DIR
from scripts.find_bbox import find_min_max
from tests.common import TESTS_DIR, config as default_test_config, test_resources_path


@pytest.fixture
def bounding_box():
    file_path = TESTS_DIR / "bbox_test.osm"
    with open(file_path, 'rb') as f:
        return f.read()


@pytest.fixture
def renumber_test_files():
    input_file = str(TESTS_DIR / "renumber_test.osm")
    output_file = str(TESTS_DIR / "renumber_test_output.osm")
    return input_file, output_file


@pytest.fixture
def sort_test_files():
    input_file = str(TESTS_DIR / "sort_test.osm")
    output_file = str(TESTS_DIR / "sort_test_output.osm")
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
def test_run_osm2pgsql_cmd(db_connection, test_schema, test_tables):
    style_file_path = str(TESTS_DIR / "test_default.lua")
    input_file = str(TESTS_DIR / "bbox_test.osm")

    test_config = deepcopy(default_test_config)
    test_config.importer.input_file = input_file
    test_config.importer.style_file = style_file_path
    test_config.importer.schema = test_schema


    run_osm2pgsql_cmd(test_config)

    expected_count = {test_tables[0]: 6, test_tables[1]: 0, test_tables[2]: 1}

    cursor = db_connection.cursor()
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
    run_osmium_cmd('s', str(input_file), str(output_file))
    assert os.path.exists(output_file)

    with open(output_file, 'r') as f:
        content = f.read()
    assert is_sorted_by_id(content, 'node') == True
    assert is_sorted_by_id(content, 'way') == True
    assert is_sorted_by_id(content, 'relation') == True

    os.remove(output_file)


def test_run_osmium_cmd_sort_renumber(mock_subprocess_run, mock_remove):
    mock_subprocess_run.side_effect = [subprocess.CompletedProcess(args=[], returncode=0),  # for sort
                                       subprocess.CompletedProcess(args=[], returncode=0)]  # for renumber

    input_file = 'test_input.osm'
    output_file = 'test_output.osm'
    tmp_file = 'tmp.osm'

    run_osmium_cmd('sr', input_file, output_file)
    # both sort and renumbering occurred
    assert mock_subprocess_run.call_count == 2
    mock_subprocess_run.assert_any_call(["osmium", "sort", input_file, "-o", tmp_file])
    mock_subprocess_run.assert_any_call(["osmium", "renumber", tmp_file, "-o", output_file])

    # tmp_file was deleted
    mock_remove.assert_called_once_with(tmp_file)


def test_import_to_db_invalid_file():
    with pytest.raises(FileNotFoundError, match="No valid file to import was found."):
        test_config = deepcopy(default_test_config)
        test_config.input_file = resources.path(test_resources_path, "id_test.osm")
        import_osm_to_db(test_config)


def test_main_invalid_inputfile():
    arg_list = ["d", "invalid_file.osm"]
    with pytest.raises(FileNotFoundError, match="File 'invalid_file.osm' does not exist."):
        main(arg_list)


def test_invalid_inputfile_extension():
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
        arg_list = ["d", tmp_file.name]
        with pytest.raises(InvalidInputError,
                           match="File must have one of the following extensions: osm, osm.pbf, osm.bz2"):
            main(arg_list)


@pytest.mark.parametrize("test_input", ["d", "i", "ie"])
def test_main_diie_valid(mocker, test_input):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = [test_input, tmp_file.name]
        mock_run_osmium_cmd = mocker.patch('scripts.process_osm.run_osmium_cmd')
        main(arg_list)
        mock_run_osmium_cmd.assert_called_once_with(arg_list[0], arg_list[1])


@pytest.mark.parametrize("test_input", ["s", "r", "sr"])
def test_main_srsr_invalid(test_input):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = [test_input, tmp_file.name]
        with pytest.raises(MissingInputError, match="An output file must be specified with '-o' flag."):
            main(arg_list)


@pytest.mark.parametrize("test_input", ["s", "r", "sr"])
def test_main_srsr_valid(mocker, test_input):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = [test_input, tmp_file.name, "-o", " output.osm"]
        mock_run_osmium_cmd = mocker.patch('scripts.process_osm.run_osmium_cmd')
        main(arg_list)
        mock_run_osmium_cmd.assert_called_once_with(arg_list[0], arg_list[1], arg_list[3])


def test_main_input_style_valid(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_input, tempfile.NamedTemporaryFile(suffix=".lua") as tmp_lua:
        arg_list = ["u", tmp_input.name, "-l", tmp_lua.name]
        mock_import_osm_to_db = mocker.patch('scripts.process_osm.import_osm_to_db')
        main(arg_list)
        mock_import_osm_to_db.assert_called_once_with(arg_list[1], False, False, arg_list[3], "public")


def test_main_style_file_invalid():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["u", tmp_file.name, "-l", "invalid_style.lua"]
        with pytest.raises(FileNotFoundError, match="File 'invalid_style.lua' does not exist."):
            main(arg_list)


def test_main_style_file_extension_invalid():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file, tempfile.NamedTemporaryFile(
        suffix=".txt") as invalid_lua:
        arg_list = ["u", tmp_file.name, "-l", invalid_lua.name]
        with pytest.raises(InvalidInputError, match="File must have the '.lua' extension."):
            main(arg_list)


# relation_id missing
def test_main_bbox_id_missing():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name]
        with pytest.raises(MissingInputError, match="Existing relation ID must be specified."):
            main(arg_list)


def test_postprocess_osm_import_invalid_style(mock_subprocess_run, test_schema):
    mock_subprocess_run.return_value.returncode = 0
    test_config = deepcopy(default_test_config)
    test_config.importer.style_file = resources.path(test_resources_path, "simple.lua")
    test_config.importer.schema = test_schema

    postprocess_osm_import(test_config)
    mock_subprocess_run.assert_not_called()
