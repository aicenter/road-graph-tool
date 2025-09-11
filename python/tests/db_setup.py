import pytest

from importlib.resources import files

import roadgraphtool.db

from roadgraphtool.config import parse_config_file


test_resources_path = "tests.resources"

test_config_file = files(test_resources_path).joinpath("config.yaml")

config = parse_config_file(test_config_file)

roadgraphtool.db.init_db(config)

# create test schema if it doesn't exist
roadgraphtool.db.db.execute_sql(f"CREATE SCHEMA IF NOT EXISTS test_schema;")


@pytest.fixture
def test_tables():
    # must match tables defined in /data/test_default.lua
    return ['test_nodes', 'test_ways', 'test_relations']

@pytest.fixture
def test_schema():
    return 'test_schema'

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