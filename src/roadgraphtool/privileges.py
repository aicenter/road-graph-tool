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
    Grant the role the privileges needed to work with Road Graph Tool:

    - ``CONNECT`` and ``TEMPORARY`` on the database (the procedures use temporary tables).
    - ``CREATE`` on the database, to create schemas for new road networks (root config parameter
      ``create_schema``, and the staging schema of the ``osm_file`` import). The role owns the schemas it
      creates, and therefore all tables, functions, and procedures installed into them, so no further grants
      are needed there.
    - ``USAGE`` on schema ``public``, where the extensions (PostGIS, pgRouting, hstore) live.
    - Read access to the road network in *schema*.

    The role must exist. The privileges are granted by the user configured for the database connection,
    so it has to own the objects (or have the right to grant privileges on them).
    """
    quote = postgresql.dialect().identifier_preparer.quote
    role_identifier = quote(role)
    schema_identifier = quote(schema)

    logging.info("Granting Road Graph Tool privileges in database '%s' to role '%s'", db_name, role)
    db.execute_sql(f"GRANT CONNECT, TEMPORARY, CREATE ON DATABASE {quote(db_name)} TO {role_identifier}")
    db.execute_sql(f"GRANT USAGE ON SCHEMA public TO {role_identifier}")
    db.execute_sql(f"GRANT USAGE ON SCHEMA {schema_identifier} TO {role_identifier}")
    db.execute_sql(
        f"GRANT SELECT ON {', '.join(f'{schema_identifier}.{table}' for table in RGT_READ_TABLES)} TO {role_identifier}"
    )
    db.execute_sql(
        f"GRANT EXECUTE ON FUNCTION {', '.join(f'{schema_identifier}.{function}' for function in RGT_FUNCTIONS)} "
        f"TO {role_identifier}"
    )
