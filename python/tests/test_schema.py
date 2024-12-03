import pytest

from roadgraphtool.schema import create_schema, add_postgis_extension, check_empty_or_nonexistent_tables
from roadgraphtool.db import db

@pytest.mark.usefixtures("teardown_db")
def test_schema_creation():
    schema = 'test_schema'
    create_schema(schema)
    
    cursor = db.get_new_cursor()
    cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s;", (schema,))
    result = cursor.fetchone()
    cursor.close()
    
    assert result is not None
    assert result[0] == schema

@pytest.mark.usefixtures("teardown_db")
def test_add_postgis_extension():
    schema = 'test_schema'
    
    create_schema(schema)
    add_postgis_extension(schema)

    cursor = db.get_new_cursor()
    cursor.execute("SELECT * FROM pg_extension WHERE extname = 'postgis';")
    result = cursor.fetchone()
    cursor.close()
    
    assert result is not None

@pytest.mark.usefixtures("teardown_db")
def test_check_empty_or_nonexistent_tables_empty(test_schema):
    
    create_schema(test_schema)
    result = check_empty_or_nonexistent_tables(test_schema, test_schema)
    assert result is True

@pytest.mark.usefixtures("teardown_db")
def test_check_empty_or_nonexistent_tables_not_empty(test_schema, test_tables):
    create_schema(test_schema)
    
    cursor = db.get_new_cursor()
    cursor.execute(f"CREATE TABLE if not exists {test_schema}.{test_tables[0]} (id SERIAL PRIMARY KEY);")
    cursor.execute(f"INSERT INTO {test_schema}.{test_tables[0]}(id) VALUES (1);")
    db.commit()
    
    result = check_empty_or_nonexistent_tables(test_schema, test_tables)

    assert result is False