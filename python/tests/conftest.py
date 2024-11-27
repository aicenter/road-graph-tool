import pytest

from roadgraphtool.schema import get_connection

@pytest.fixture(scope="module")
def test_tables():
    # must match tables defined in /data/test_default.lua
    return ['test_nodes', 'test_ways', 'test_relations']

@pytest.fixture(scope="module")
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

@pytest.fixture(scope="module")
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

@pytest.fixture(scope="module")
def setup_test_schema(test_schema, test_tables_elevation):
    create_schema_query = f"CREATE SCHEMA IF NOT EXISTS {test_schema};"
    drop_schema_query = f"DROP SCHEMA IF EXISTS {test_schema} CASCADE;"
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {test_schema}.{test_tables_elevation[0]} (
        node_id BIGINT NOT NULL,
        geom geometry(Point, 4326) NOT NULL,
        tags jsonb
    );
    """
    insert_query = f"""
    INSERT INTO {test_schema}.{test_tables_elevation[0]} (node_id, geom)
    values
    (1, st_setsrid(st_makepoint(45.0, -93.0), 4326)),
    (2, st_setsrid(st_makepoint(46.0, -94.0), 4326)),
    (3, st_setsrid(st_makepoint(47.0, -95.0), 4326));
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_schema_query)
            cur.execute(create_table_query)
            cur.execute(insert_query)
        conn.commit()

    yield test_schema

    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in test_tables_elevation:
                cur.execute(f"DROP TABLE IF EXISTS {test_schema}.{table};")
            cur.execute(drop_schema_query)
        conn.commit()
