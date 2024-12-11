import pytest

from pathlib import Path
from importlib.resources import files

import roadgraphtool.db

from roadgraphtool.config import parse_config_file


TESTS_DIR = Path(__file__).parent.parent.parent / "python/tests/data"

test_resources_path = "tests.data"

test_config_file = files(test_resources_path).joinpath("config.yaml")

config = parse_config_file(test_config_file)

# default style file
style_file = files('roadgraphtool.resources.lua_styles').joinpath("pipeline.lua")
config.importer.style_file = style_file

roadgraphtool.db.init_db(config)


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

# @pytest.fixture(scope="function")
# def db_connection():
#     conn = get_connection()
#     yield conn
#     conn.close()

@pytest.fixture
def teardown_db(request, test_schema, test_tables):
    def cleanup():
        cursor = roadgraphtool.db.db.get_new_cursor()
        for table in test_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {test_schema}.{table};")
        cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE;")
        roadgraphtool.db.db.commit()
        cursor.close()
    request.addfinalizer(cleanup)
