import re
from pathlib import Path

import pytest

from roadgraphtool.sql_install import (
    DEFAULT_SQL_DIR,
    _COMMENT,
    _TABLE_DEFINITION,
    _ddl_columns,
    _install_tables,
    _normalize_definition,
    _statements,
    _update_statements,
)

_CREATE_TABLE = """CREATE TABLE IF NOT EXISTS {schema}.things (
    id integer NOT NULL,
    "position" smallint,
    geom public.geometry(Point, 4326) NOT NULL
)"""
_COMMENT_ON = "COMMENT ON COLUMN {schema}.things.geom IS 'Where the thing is; a statement with a semicolon'"
_CREATE_SEQUENCE = "CREATE SEQUENCE IF NOT EXISTS {schema}.things_id_seq\n    START WITH 1"
_SET_DEFAULT = (
    "ALTER TABLE ONLY {schema}.things ALTER COLUMN id SET DEFAULT nextval('{schema}.things_id_seq'::regclass)"
)
_SET_OPTIONS = "ALTER TABLE ONLY {schema}.things ALTER COLUMN id SET (n_distinct=-0.5)"
_ADD_CONSTRAINT = "ALTER TABLE ONLY {schema}.things\n    ADD CONSTRAINT things_pk PRIMARY KEY (id)"
_CREATE_INDEX = "CREATE INDEX things_geom_index ON {schema}.things USING gist (geom)"
_STATEMENTS = [_CREATE_TABLE, _COMMENT_ON, _CREATE_SEQUENCE, _SET_DEFAULT, _SET_OPTIONS, _ADD_CONSTRAINT, _CREATE_INDEX]

_TABLE_SQL = (
    "--\n-- Name: things; Type: TABLE; Schema: public\n--\n"
    + _CREATE_TABLE + ";\n\n"
    + _COMMENT_ON + ";\n\n"
    + _CREATE_SEQUENCE + ";\n\n"
    + _SET_DEFAULT + ";\n"
    + _SET_OPTIONS + ";\n\n"
    + "-- Name: things things_pk; Type: CONSTRAINT; Schema: public\n"
    + _ADD_CONSTRAINT + ";\n"
    + _CREATE_INDEX + ";\n"
)


class FakeDb:
    """Answers the catalog queries of the installer from the given existing objects and records executed statements.

    *tables*: table name -> column names; *constraints*: (table, name, type, definition) rows;
    *indexes*: index name -> definition.
    """

    def __init__(self, tables=None, constraints=(), indexes=None):
        self.tables = tables or {}
        self.constraints = list(constraints)
        self.indexes = indexes or {}
        self.executed = []

    def execute_sql_and_fetch_all_rows(self, sql, params):
        if "information_schema.tables" in sql:
            if params["table"] not in self.tables:
                return []
            return [(column,) for column in self.tables[params["table"]]] or [(None,)]
        if "pg_constraint" in sql:
            return self.constraints
        if "pg_indexes" in sql:
            return list(self.indexes.items())
        raise AssertionError(f"unexpected query {sql}")

    def execute_statements(self, statements, schema):
        self.executed.append((schema, list(statements)))


@pytest.fixture
def sql_dir(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "01_things.sql").write_text(_TABLE_SQL, encoding="utf-8")
    return tmp_path


def test_statements_are_split_outside_of_string_literals():
    assert _statements(_COMMENT.sub("", _TABLE_SQL)) == _STATEMENTS


def test_ddl_columns():
    body = _TABLE_DEFINITION.match(_CREATE_TABLE).group(2)

    assert _ddl_columns(body) == {
        "id": "id integer NOT NULL",
        "position": '"position" smallint',
        "geom": "geom public.geometry(Point, 4326) NOT NULL",
    }


def test_missing_table_is_created_with_the_whole_ddl(sql_dir):
    db = FakeDb()

    _install_tables(db, sql_dir, "public")

    assert db.executed == [("public", _STATEMENTS)]


_THINGS_PK = ("things", "things_pk", "p", "PRIMARY KEY (id)")
_THINGS_GEOM_INDEX = {"things_geom_index": "CREATE INDEX things_geom_index ON public.things USING gist (geom)"}


def test_existing_table_matching_the_ddl_only_gets_the_idempotent_statements(sql_dir):
    db = FakeDb(tables={"things": ["id", "position", "geom"]}, constraints=[_THINGS_PK], indexes=_THINGS_GEOM_INDEX)

    _install_tables(db, sql_dir, "public")

    assert db.executed == [("public", [_COMMENT_ON, _CREATE_SEQUENCE, _SET_DEFAULT, _SET_OPTIONS])]


def test_missing_column_constraint_and_index_are_added(sql_dir):
    db = FakeDb(tables={"things": ["id", "geom"]}, constraints=[("other", "things_pk", "p", "PRIMARY KEY (id)")])

    _install_tables(db, sql_dir, "public")

    assert db.executed == [
        (
            "public",
            [
                'ALTER TABLE {schema}.things ADD COLUMN "position" smallint',
                _COMMENT_ON,
                _CREATE_SEQUENCE,
                _SET_DEFAULT,
                _SET_OPTIONS,
                _ADD_CONSTRAINT,
                _CREATE_INDEX,
            ],
        )
    ]


def test_partially_existing_tables_are_completed(sql_dir):
    (sql_dir / "tables" / "01_things.sql").write_text(
        _TABLE_SQL + _TABLE_SQL.replace("things", "other_things"), encoding="utf-8"
    )
    db = FakeDb(tables={"things": ["id", "position", "geom"]}, constraints=[_THINGS_PK], indexes=_THINGS_GEOM_INDEX)

    _install_tables(db, sql_dir, "public")

    [(_, statements)] = db.executed
    assert _CREATE_TABLE.replace("things", "other_things") in statements
    assert _ADD_CONSTRAINT.replace("things", "other_things") in statements
    assert _CREATE_TABLE not in statements
    assert _ADD_CONSTRAINT not in statements


def test_quoted_constraint_and_index_names_are_matched():
    table_sql = (
        'ALTER TABLE ONLY {schema}.things ADD CONSTRAINT "Things PK" PRIMARY KEY (id);\n'
        'CREATE UNIQUE INDEX IF NOT EXISTS "Things Index" ON {schema}.things (id);\n'
    )
    constraints = {"things": {"Things PK": ("p", "PRIMARY KEY (id)")}}
    indexes = {"Things Index": 'CREATE UNIQUE INDEX "Things Index" ON public.things USING btree (id)'}

    assert _update_statements(FakeDb(), "public", table_sql, constraints, indexes) == []


@pytest.mark.parametrize(
    "ddl, catalog",
    [
        ("PRIMARY KEY (id)", "PRIMARY KEY (id)"),
        ('UNIQUE (way_id, "position")', 'UNIQUE (way_id, "position")'),
        ("FOREIGN KEY (node_id) REFERENCES {schema}.nodes(id) ON DELETE CASCADE",
         "FOREIGN KEY (node_id) REFERENCES public.nodes(id) ON DELETE CASCADE"),
        ('foreign key ("from")\n    references {schema}."Nodes" (id)', 'FOREIGN KEY ("from") REFERENCES "Nodes"(id)'),
    ],
)
def test_ddl_and_catalog_definitions_normalize_equally(ddl, catalog):
    assert _normalize_definition(ddl, "public") == _normalize_definition(catalog, "public")


def test_constraint_existing_under_another_name_is_renamed():
    constraints = {"things": {"areas_pkey_old": ("p", "PRIMARY KEY (id)")}}

    statements = _update_statements(FakeDb(), "public", _ADD_CONSTRAINT + ";", constraints, {})

    assert statements == ['ALTER TABLE ONLY {schema}.things RENAME CONSTRAINT "areas_pkey_old" TO things_pk']


def test_constraint_with_changed_definition_is_replaced():
    constraints = {"things": {"things_pk": ("p", "PRIMARY KEY (id, geom)")}}

    statements = _update_statements(FakeDb(), "public", _ADD_CONSTRAINT + ";", constraints, {})

    assert statements == [
        "ALTER TABLE ONLY {schema}.things DROP CONSTRAINT things_pk, ADD CONSTRAINT things_pk PRIMARY KEY (id)"
    ]


def test_differently_named_and_defined_primary_key_is_replaced():
    constraints = {"things": {"old_pk": ("p", "PRIMARY KEY (geom)"), "things_fk": ("f", "FOREIGN KEY (id) REFERENCES t(id)")}}

    statements = _update_statements(FakeDb(), "public", _ADD_CONSTRAINT + ";", constraints, {})

    assert statements == [
        'ALTER TABLE ONLY {schema}.things DROP CONSTRAINT "old_pk", ADD CONSTRAINT things_pk PRIMARY KEY (id)'
    ]


def test_non_primary_constraint_with_new_definition_is_added():
    table_sql = "ALTER TABLE ONLY {schema}.things ADD CONSTRAINT things_fk FOREIGN KEY (id) REFERENCES {schema}.t(id);"
    constraints = {"things": {"things_pk": ("p", "PRIMARY KEY (id)"), "other_fk": ("f", "FOREIGN KEY (geom) REFERENCES t(id)")}}

    statements = _update_statements(FakeDb(), "public", table_sql, constraints, {})

    assert statements == [
        "ALTER TABLE ONLY {schema}.things ADD CONSTRAINT things_fk FOREIGN KEY (id) REFERENCES {schema}.t(id)"
    ]


def test_index_existing_under_another_name_is_renamed():
    indexes = {"old_geom_index": "CREATE INDEX old_geom_index ON public.things USING gist (geom)"}

    statements = _update_statements(FakeDb(), "public", _CREATE_INDEX + ";", {}, indexes)

    assert statements == ['ALTER INDEX {schema}."old_geom_index" RENAME TO things_geom_index']


def test_index_with_other_definition_is_created():
    indexes = {"things_id_index": "CREATE INDEX things_id_index ON public.things USING btree (id)",
               "unique_geom": "CREATE UNIQUE INDEX unique_geom ON public.things USING gist (geom)"}

    statements = _update_statements(FakeDb(), "public", _CREATE_INDEX + ";", {}, indexes)

    assert statements == [_CREATE_INDEX]


def test_unsupported_statement_fails(sql_dir):
    (sql_dir / "tables" / "01_things.sql").write_text(
        _TABLE_SQL + "DROP TABLE {schema}.things;\n", encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="Unsupported statement") as error:
        _install_tables(FakeDb(), sql_dir, "public")

    assert "DROP TABLE {schema}.things" in str(error.value)


def test_all_table_ddl_files_are_parsed():
    for table_sql_path in sorted((DEFAULT_SQL_DIR / "tables").glob("*.sql")):
        table_sql = _COMMENT.sub("", table_sql_path.read_text(encoding="utf-8"))
        statements = _statements(table_sql)
        tables = [match for match in map(_TABLE_DEFINITION.match, statements) if match]
        assert len(tables) == len(re.findall(r"create\s+table", table_sql, re.IGNORECASE)), table_sql_path.name
        for table in tables:
            assert _ddl_columns(table.group(2)), f"{table_sql_path.name}: no columns parsed for {table.group(1)}"
        # every statement of the shipped DDL is one the installer knows how to apply
        _update_statements(FakeDb(), "public", table_sql, {}, {})
