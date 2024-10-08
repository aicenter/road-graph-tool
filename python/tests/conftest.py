import psycopg2
import pytest

from roadgraphtool.credentials_config import CREDENTIALS as config

@pytest.fixture
def test_tables():
    # must match tables defined in /data/test_default.lua
    return ['test_nodes', 'test_ways', 'test_relations']

@pytest.fixture
def test_schema():
    return 'osm_testing'

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
def teardown_db(db_connection, request, test_schema, test_tables):
    def cleanup():
        cursor = db_connection.cursor()
        for table in test_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {test_schema}.{table};")
        db_connection.commit()
        cursor.close()
    request.addfinalizer(cleanup)