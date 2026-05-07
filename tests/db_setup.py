import os
from pathlib import Path

import pytest

import roadgraphtool.db
from roadgraphtool.config import parse_config_file

test_resources_path = Path(__file__).resolve().parent / "resources"
test_config_file = test_resources_path / "config.yaml"

_cwd = os.getcwd()
os.chdir(test_resources_path)
try:
    config = parse_config_file(test_config_file)
finally:
    os.chdir(_cwd)

setattr(config, "config_dir", test_resources_path)

roadgraphtool.db.init_db(config)

roadgraphtool.db.db.execute_sql("CREATE SCHEMA IF NOT EXISTS test_schema;")


@pytest.fixture
def test_tables():
    return ["test_nodes", "test_ways", "test_relations"]


@pytest.fixture
def test_schema():
    return "test_schema"


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
