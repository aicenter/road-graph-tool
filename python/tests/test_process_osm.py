import pathlib
import pytest
import subprocess
import psycopg2
from scripts.find_bbox import find_min_max
from roadgraphtool.credentials_config import CREDENTIALS as config

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")

@pytest.fixture
def bounding_box():
    parent_dir = pathlib.Path(__file__).parent
    file_path = str(parent_dir) + "/data/test.osm"
    with open(file_path, 'rb') as f:
        return f.read()

def test_find_mix_max(bounding_box):
    min_lon, min_lat, max_lon, max_lat = find_min_max(bounding_box)
    assert min_lon == 15.0
    assert min_lat == 5.0
    assert max_lon == 30.0
    assert max_lat == 15.0

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

@pytest.mark.usefixtures("teardown_db")
def test_command_execution_and_db_verification(db_connection):
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