import re
from pathlib import Path

import pytest

from roadgraphtool.sql_install import DEFAULT_SQL_DIR, _COMMENT, _TABLE_DEFINITION, _ddl_columns, _install_tables

_TABLE_SQL = """--
-- Name: things; Type: TABLE; Schema: public
--
CREATE TABLE IF NOT EXISTS {schema}.things (
    id integer NOT NULL,
    "position" smallint,
    geom public.geometry(Point, 4326) NOT NULL
);

-- Name: things things_pk; Type: CONSTRAINT; Schema: public
ALTER TABLE ONLY {schema}.things
    ADD CONSTRAINT things_pk PRIMARY KEY (id);
CREATE INDEX things_geom_index ON {schema}.things USING gist (geom);
"""


class FakeDb:
    """Answers the catalog queries of the installer from the given existing objects and records executed scripts."""

    def __init__(self, tables=None, constraints=(), indexes=()):
        self.tables = tables or {}
        self.constraints = set(constraints)
        self.indexes = set(indexes)
        self.executed = []

    def execute_sql_and_fetch_all_rows(self, sql, params):
        if "information_schema.tables" in sql:
            return [(table,) for table in params["tables"] if table in self.tables]
        if "information_schema.columns" in sql:
            return [(column,) for column in self.tables[params["table"]]]
        if "pg_constraint" in sql:
            return [(constraint,) for constraint in self.constraints]
        if "pg_indexes" in sql:
            return [(index,) for index in self.indexes]
        raise AssertionError(f"unexpected query {sql}")

    def execute_script(self, script_path, schema, raise_on_error=False):
        assert raise_on_error
        self.executed.append(Path(script_path).name)


@pytest.fixture
def sql_dir(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "01_things.sql").write_text(_TABLE_SQL, encoding="utf-8")
    return tmp_path


def test_ddl_columns():
    body = _TABLE_DEFINITION.findall(_COMMENT.sub("", _TABLE_SQL))[0][1]

    assert _ddl_columns(body) == ["id", "position", "geom"]


def test_missing_table_is_created(sql_dir):
    db = FakeDb()

    _install_tables(db, sql_dir, "public")

    assert db.executed == ["01_things.sql"]


def test_existing_table_matching_the_ddl_is_kept(sql_dir):
    db = FakeDb(tables={"things": ["id", "position", "geom"]}, constraints=["things_pk"], indexes=["things_geom_index"])

    _install_tables(db, sql_dir, "public")

    assert db.executed == []


def test_existing_table_differing_from_the_ddl_fails(sql_dir):
    db = FakeDb(tables={"things": ["id", "geom"]}, indexes=["things_geom_index"])

    with pytest.raises(RuntimeError) as error:
        _install_tables(db, sql_dir, "public")

    assert "public.things: missing column position" in str(error.value)
    assert "missing constraint things_pk" in str(error.value)
    assert "things_geom_index" not in str(error.value)
    assert db.executed == []


def test_partially_existing_tables_fail(sql_dir):
    (sql_dir / "tables" / "01_things.sql").write_text(
        _TABLE_SQL + _TABLE_SQL.replace("things", "other_things"), encoding="utf-8"
    )
    db = FakeDb(tables={"things": ["id", "position", "geom"]})

    with pytest.raises(RuntimeError, match="only some of the tables exist"):
        _install_tables(db, sql_dir, "public")


def test_all_table_ddl_files_are_parsed():
    for table_sql_path in sorted((DEFAULT_SQL_DIR / "tables").glob("*.sql")):
        table_sql = _COMMENT.sub("", table_sql_path.read_text(encoding="utf-8"))
        tables = _TABLE_DEFINITION.findall(table_sql)
        assert len(tables) == len(re.findall(r"create\s+table", table_sql, re.IGNORECASE)), table_sql_path.name
        for name, body in tables:
            assert _ddl_columns(body), f"{table_sql_path.name}: no columns parsed for {name}"
