from types import SimpleNamespace
from unittest.mock import patch

import pytest

import roadgraphtool.schema
from roadgraphtool.db import Database
from roadgraphtool.exceptions import MissingInputError


def _config(**kwargs):
    return SimpleNamespace(schema="pedestrian", db=SimpleNamespace(db_name="rgt"), **kwargs)


@pytest.fixture
def schema_mocks():
    with (
        patch.object(roadgraphtool.schema, "schema_exists") as exists,
        patch.object(roadgraphtool.schema, "create_schema") as create,
        patch("roadgraphtool.sql_install.install_sql") as install,
    ):
        yield exists, create, install


def test_existing_schema_is_used(schema_mocks):
    exists, create, install = schema_mocks
    exists.return_value = True

    roadgraphtool.schema.ensure_schema(_config(create_schema=True))

    create.assert_not_called()
    install.assert_not_called()


def test_missing_schema_raises_without_create_schema(schema_mocks):
    exists, create, install = schema_mocks
    exists.return_value = False

    with pytest.raises(MissingInputError, match="create_schema"):
        roadgraphtool.schema.ensure_schema(_config())

    create.assert_not_called()
    install.assert_not_called()


def test_missing_schema_raises_with_create_schema_false(schema_mocks):
    exists, _, _ = schema_mocks
    exists.return_value = False

    with pytest.raises(MissingInputError):
        roadgraphtool.schema.ensure_schema(_config(create_schema=False))


def test_missing_schema_is_created_and_installed_with_create_schema(schema_mocks):
    exists, create, install = schema_mocks
    exists.return_value = False
    config = _config(create_schema=True)

    roadgraphtool.schema.ensure_schema(config)

    create.assert_called_once_with("pedestrian")
    install.assert_called_once()
    assert install.call_args.kwargs["config"] is config
    assert install.call_args.kwargs["include_tests"] is False


def test_search_path_public():
    assert Database.search_path("public") == "public"


def test_search_path_other_schema_keeps_public_for_extensions():
    assert Database.search_path("pedestrian") == '"pedestrian", public'


def test_connection_options_set_search_path():
    database = Database()
    database.schema = "pedestrian"

    assert database._connection_options() == '-c search_path="pedestrian",public'


def test_connection_options_escape_spaces():
    database = Database()
    database.schema = "my schema"

    assert database._connection_options() == '-c search_path="my\\ schema",public'
