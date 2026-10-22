# Multiple networks in one schema

Status: analysis only, not implemented. Today, each network profile (car, pedestrian) needs its own database schema. This document records why, and what it would take to store several networks of the same region in one schema.

Written in October 2026, when the [pedestrian profile](../README.md#pedestrian-profile) was added for the Shared stops experiment.


## What already works
If each network gets its own `areas` row (the same polygon under a new id), part of the pipeline output is already separated by area id:

- `edges.area` keeps the edges of the two networks apart, and the export selects edges by `edges.area`.
- `component_data` has the primary key `(node_id, area)`, so the strong components of each network are stored separately.


## Blockers
The rest of the pipeline assumes one network per schema.

| Blocker | Where | Effect with two networks |
|---|---|---|
| Way selection is spatial only | [`function_get_ways_in_target_area.sql`](../src/roadgraphtool/SQL/functions/function_get_ways_in_target_area.sql), and the way selection in [`procedure_compute_speeds_for_segments.sql`](../src/roadgraphtool/SQL/procedures/procedure_compute_speeds_for_segments.sql) and [`procedure_compute_speeds_from_neigborhood_segments.sql`](../src/roadgraphtool/SQL/procedures/procedure_compute_speeds_from_neigborhood_segments.sql) | Every way intersecting the area polygon is used. Car contraction would include footways, and the pedestrian graph would include motorways. |
| One direction per way | `ways.oneway` in [`04_ways.sql`](../src/roadgraphtool/SQL/tables/04_ways.sql) | A street can be one-way for cars and two-way for pedestrians. Only one of them can be stored. |
| Global contraction flag | `nodes.contracted` in [`03_nodes.sql`](../src/roadgraphtool/SQL/tables/03_nodes.sql), set and read in [`procedure_contract_graph_in_area.sql`](../src/roadgraphtool/SQL/procedures/procedure_contract_graph_in_area.sql), read in [`function_select_network_nodes_in_area.sql`](../src/roadgraphtool/SQL/functions/function_select_network_nodes_in_area.sql) | A node contracted in one network is also excluded from the other network's edges and export. The flag is never reset. |
| Strong components select edges by geometry | [`procedure_compute_strongly_connected_components.sql`](../src/roadgraphtool/SQL/procedures/procedure_compute_strongly_connected_components.sql) uses `st_within(edges.geom, area.geom)` | Edges of both networks enter one component computation. |
| Overpass import has no conflict handling | `_run_overpass_backend` in [`overpass_import.py`](../src/roadgraphtool/overpass_import.py) appends to `nodes`, `ways`, `nodes_ways` | OSM nodes and ways present in both networks raise primary-key violations on the second import. The `osm_file` backend already skips existing rows in the `copy_*` functions of [`process_osm.py`](../src/roadgraphtool/process_osm.py). |

The OSM ids are primary keys of `nodes` and `ways`, and `nodes_ways` is unique on `(way_id, position)`. Storing each OSM object once is fine, because its geometry does not depend on the network. Only the network membership and the direction do.


## Proposed changes
1. **Network membership table** `network_ways(area, way_id, oneway)`, primary key `(area, way_id)`, foreign keys to `areas` and `ways`.
    - Both import backends insert one row per imported way, with the direction given by the profile.
    - `get_ways_in_target_area` joins `network_ways` on `area = target_area_id` and returns its `oneway`. The speed procedures use the same join.
    - `ways.oneway` stays for backward compatibility but is no longer read.
2. **Contraction state per run instead of the global flag.**
    - In `contract_graph_in_area`, decide whether a node is contracted by looking it up in the temporary `contractions` table, not by `nodes.contracted`.
    - In `select_network_nodes_in_area`, drop the `contracted = FALSE` condition. The `component_data` rows of an area only contain endpoints of that area's edges, which are exactly its non-contracted nodes.
    - Keep the column and keep setting it, marked as deprecated.
3. **Strong components** select edges by `edges.area = target_area_id`, as the export already does.
4. **Overpass import** writes `nodes`, `ways` and `nodes_ways` through temporary tables and `INSERT … ON CONFLICT DO NOTHING`.
5. **Migration script** creating `network_ways` and filling it from the existing `ways` rows (`area`, `id`, `oneway`), so existing car schemas keep working.
6. **Provenance columns.** `ways.area`, `nodes.area` and `nodes_ways.area` then only mean "first imported with this area". The legacy [`procedure_add_temp_map.sql`](../src/roadgraphtool/SQL/procedures/procedure_add_temp_map.sql) deletes by these columns and would delete rows shared with another network; document this or remove the procedure.
7. **Tests.** Update the pgTAP fixtures of the contraction, restricted-node and `get_ways_in_target_area` tests to fill `network_ways`. Add tests that two areas with the same polygon and different way sets produce disjoint edge sets, and that contracting one area does not change the node selection of the other.


## Side benefit
Changes 2 and 3 also fix overlapping car areas in one schema. These already hit the global contraction flag and the geometry-based strong components today.


## Trade-off
Separate schemas already give consistent ids across networks: node and way ids are OSM ids, exported as `db_id`, unless the input was renumbered with `process_osm.py r`. So a car node and a pedestrian node at the same OSM node can be matched without a shared schema.

A shared schema mainly buys:

- one import of the common nodes and ways instead of two,
- joint SQL queries over both networks without cross-schema joins.

The cost is the table and migration above, edits to six SQL functions and procedures and the Overpass import, and the test updates. For the Shared stops experiment, separate schemas were chosen.
