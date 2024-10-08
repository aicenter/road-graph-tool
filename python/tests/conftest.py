import psycopg2
import pytest

from roadgraphtool.credentials_config import CREDENTIALS as config
from tests.test_filter_osm import TESTS_DIR

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")

@pytest.fixture(scope="function")
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