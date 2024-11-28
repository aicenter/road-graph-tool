import pytest


@pytest.fixture
def test_tables():
    # must match tables defined in /data/test_default.lua
    return ['test_nodes', 'test_ways', 'test_relations']

@pytest.fixture
def test_schema():
    return 'test_schema'

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")

@pytest.fixture
def mock_remove(mocker):
    return mocker.patch("os.remove")

@pytest.fixture(scope="function")
def db_connection():
    conn = get_connection()
    yield conn
    conn.close()

@pytest.fixture
def teardown_db(db_connection, request, test_schema, test_tables):
    def cleanup():
        cursor = db_connection.cursor()
        for table in test_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {test_schema}.{table};")
        cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE;")
        db_connection.commit()
        cursor.close()
    request.addfinalizer(cleanup)
