"""
Public API for granting database privileges needed to work with Road Graph Tool data.

This module is intentionally importable from client projects so they can grant the road-graph-tool
privileges first and then add their own, analogously to `roadgraphtool.sql_install`.
"""

from __future__ import annotations

import logging

from sqlalchemy.dialects import postgresql

from roadgraphtool.db import db

# Read access to the processed road network (nodes, edges, OSM ways and tags, strong components).
RGT_READ_TABLES = [
    "areas",
    "nodes",
    "edges",
    "component_data",
    "nodes_ways",
    "ways",
    "ways_tags",
    "tags",
]

RGT_FUNCTIONS = [
    "select_network_nodes_in_area(smallint)",
]


def grant_privileges(*, db_name: str, role: str, schema: str = "public") -> None:
    """
    Grant the role the privileges needed to read the road network data processed by Road Graph Tool.

    The role must exist. The privileges are granted by the user configured for the database connection,
    so it has to own the objects (or have the right to grant privileges on them).
    """
    quote = postgresql.dialect().identifier_preparer.quote
    role_identifier = quote(role)
    schema_identifier = quote(schema)

    logging.info("Granting Road Graph Tool privileges in database '%s' to role '%s'", db_name, role)
    db.execute_sql(f"GRANT CONNECT, TEMPORARY ON DATABASE {quote(db_name)} TO {role_identifier}")
    db.execute_sql(f"GRANT USAGE ON SCHEMA {schema_identifier} TO {role_identifier}")
    db.execute_sql(
        f"GRANT SELECT ON {', '.join(f'{schema_identifier}.{table}' for table in RGT_READ_TABLES)} TO {role_identifier}"
    )
    db.execute_sql(
        f"GRANT EXECUTE ON FUNCTION {', '.join(f'{schema_identifier}.{function}' for function in RGT_FUNCTIONS)} "
        f"TO {role_identifier}"
    )
