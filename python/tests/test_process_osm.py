import pathlib
import tempfile
import pytest
import subprocess
import os
import psycopg2
import xml.etree.ElementTree as ET

from roadgraphtool.credentials_config import CREDENTIALS as config
from scripts.process_osm import run_osmium_cmd, main, import_osm_to_db
from scripts.find_bbox import find_min_max
from scripts.filter_osm import MissingInputError, InvalidInputError

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")

@pytest.fixture
def bounding_box():
    parent_dir = pathlib.Path(__file__).parent
    file_path = str(parent_dir) + "/data/bbox_test.osm"
    with open(file_path, 'rb') as f:
        return f.read()

@pytest.fixture(scope="module")
def db_connection():
    conn = psycopg2.connect(
        dbname=config.db_name,
        user=config.username,
        password=config.db_password,
        host=config.db_host,
        port=config.db_server_port
    )
    yield conn
    conn.close()

@pytest.fixture
def teardown_db(db_connection, request):
    def cleanup():
        cursor = db_connection.cursor()
        cursor.execute("DROP TABLE IF EXISTS mocknodes;")
        cursor.execute("DROP TABLE IF EXISTS mockways;")
        cursor.execute("DROP TABLE IF EXISTS mockrelations;")
        db_connection.commit()
        cursor.close()
    request.addfinalizer(cleanup)

@pytest.fixture
def renumber_test_files():
    parent_dir = pathlib.Path(__file__).parent
    input_file = str(parent_dir) + "/data/renumber_test.osm"
    output_file = str(parent_dir) + "/data/renumber_test_output.osm"
    return input_file, output_file 

@pytest.fixture
def sort_test_files():
    parent_dir = pathlib.Path(__file__).parent
    input_file = str(parent_dir) + "/data/sort_test.osm"
    output_file = str(parent_dir) + "/data/sort_test_output.osm"
    return input_file, output_file

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

def test_find_mix_max(bounding_box):
    min_lon, min_lat, max_lon, max_lat = find_min_max(bounding_box)
    assert min_lon == 15.0
    assert min_lat == 5.0
    assert max_lon == 30.0
    assert max_lat == 15.0

@pytest.mark.usefixtures("teardown_db")
def test_run_osm2pgsql_cmd(db_connection):
    parent_dir = pathlib.Path(__file__).parent
    style_file_path = str(parent_dir) + "/data/mock_default.lua"
    input_file = str(parent_dir) + "/data/test.osm"

    db_username = config.username
    db_host = config.db_host
    db_name = config.db_name
    db_server_port = config.db_server_port

    command = ["osm2pgsql", "-d", db_name, "-U", db_username, "-H", db_host, "-P", str(db_server_port),
               "--output=flex", "-S", style_file_path, input_file, "-x"]

    subprocess.run(command, check=True)

    cursor = db_connection.cursor()
    cursor.execute('SELECT COUNT(*) FROM mocknodes;')
    nodes_count = cursor.fetchone()[0]
    assert nodes_count == 6

    cursor.execute('SELECT COUNT(*) FROM mockways;')
    ways_count = cursor.fetchone()[0]
    assert ways_count == 0

    cursor.execute('SELECT COUNT(*) FROM mockrelations;')
    relations_count = cursor.fetchone()[0]
    assert relations_count == 1

    cursor.execute('SELECT * FROM mocknodes WHERE node_id=1;')
    node = cursor.fetchone()
    assert node is not None

    cursor.execute('SELECT * FROM mocknodes WHERE node_id=7;')
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

def test_import_to_db_valid(mocker):
    mocker.patch('os.path.exists', side_effect=lambda path: path == "resources/to_import.osm")
    mock_run_osm2pgsql_cmd = mocker.patch('scripts.process_osm.run_osm2pgsql_cmd')
    import_osm_to_db()
    mock_run_osm2pgsql_cmd.assert_called_once_with(config, 'resources/to_import.osm', 'resources/lua_styles/default.lua')

def test_missing_input():
    arg_list = ["d"]
    with pytest.raises(MissingInputError, match="Input file not provided."):
        main(arg_list)

def test_invalid_input():
    arg_list = ["d", "invalid_file.osm"]
    with pytest.raises(FileNotFoundError, match="File 'invalid_file.osm' does not exist."):
        main(arg_list)

def test_invalid_extension():
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
        arg_list = ["d", tmp_file.name]
        with pytest.raises(InvalidInputError, match="File must have one of the following extensions: osm, osm.pbf, osm.bz2"):
            main(arg_list)

@pytest.mark.parametrize("test_input", ["d", "i", "ie"])
def test_main_valid_diie(mocker, test_input):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = [test_input, tmp_file.name]
        mock_run_osmium_cmd = mocker.patch('scripts.process_osm.run_osmium_cmd')
        main(arg_list)
        mock_run_osmium_cmd.assert_called_once_with(arg_list[0], arg_list[1])

@pytest.mark.parametrize("test_input", ["s", "r", "sr"])
def test_main_invalid_srsr(test_input):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = [test_input, tmp_file.name]
        with pytest.raises(MissingInputError, match="An output file must be specified with '-o' tag."):
            main(arg_list)

@pytest.mark.parametrize("test_input", ["s", "r", "sr"])
def test_main_valid_srsr(mocker, test_input):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = [test_input, tmp_file.name, "-o", " output.osm"]
        mock_run_osmium_cmd = mocker.patch('scripts.process_osm.run_osmium_cmd')
        main(arg_list)
        mock_run_osmium_cmd.assert_called_once_with(arg_list[0], arg_list[1], arg_list[3])

def test_main_valid_default_style(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["u", tmp_file.name]
        mock_run_osm2pgsql_cmd = mocker.patch('scripts.process_osm.run_osm2pgsql_cmd')
        main(arg_list)
        mock_run_osm2pgsql_cmd.assert_called_once_with(config, arg_list[1], "resources/lua_styles/default.lua")

def test_main_valid_input_style(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_input, tempfile.NamedTemporaryFile(suffix=".lua") as tmp_lua:
        arg_list = ["u", tmp_input.name, "-l", tmp_lua.name]
        mock_run_osm2pgsql_cmd = mocker.patch('scripts.process_osm.run_osm2pgsql_cmd')
        main(arg_list)
        mock_run_osm2pgsql_cmd.assert_called_once_with(config, arg_list[1], arg_list[3])

def test_main_invalid_style_file():
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["u", tmp_file.name, "-l", "invalid_style.lua"]
        with pytest.raises(FileNotFoundError, match="File 'invalid_style.lua' does not exist."):
            main(arg_list)

def test_main_valid_bbox(mocker):
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name, "-r", "1234"]
        mock_extract_bbox = mocker.patch('scripts.process_osm.extract_bbox', return_value=(10, 20, 30, 40))
        mock_run_osm2pgsql_cmd = mocker.patch('scripts.process_osm.run_osm2pgsql_cmd')
        main(arg_list)
        mock_extract_bbox.assert_called_once_with(arg_list[3])
        mock_run_osm2pgsql_cmd.assert_called_once_with(config, arg_list[1], "resources/lua_styles/default.lua", "10,20,30,40")

def test_main_invalid_bbox():
    # relation_id missing
    with tempfile.NamedTemporaryFile(suffix=".osm") as tmp_file:
        arg_list = ["b", tmp_file.name]
        with pytest.raises(MissingInputError, match="Existing relation ID must be specified."):
            main(arg_list)