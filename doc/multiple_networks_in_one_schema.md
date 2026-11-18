# Multiple networks in one schema

Status: partly implemented. Today, each network profile (car, pedestrian) needs its own database schema. This document records why, and what it would take to store several networks of the same region in one schema.

Written in October 2026, when the [pedestrian profile](../README.md#pedestrian-profile) was added for the Shared stops experiment.

Several areas of the same network type can share one schema, see [Multiple areas in one schema](../README.md#multiple-areas-in-one-schema) in the README. The changes made for that in November 2026 removed three of the five blockers originally listed here.


## What already works
If each network gets its own `areas` row (the same polygon under a new id), the pipeline output is separated by area id:

- `edges.area` keeps the edges of the two networks apart. The contraction decides which nodes are contracted from its own run only, and the export selects edges by `edges.area`.
- `component_data` has the primary key `(node_id, area)`, and the strong components of an area are computed from the edges of that area only.
- Both import backends reuse the nodes and ways that are already in the schema.


## Blockers
The selection of the ways of a network still assumes one network per schema.

| Blocker | Where | Effect with two networks |
|---|---|---|
| Way selection is spatial only | [`function_get_ways_in_target_area.sql`](../src/roadgraphtool/SQL/functions/function_get_ways_in_target_area.sql), and the way selection in [`procedure_compute_speeds_for_segments.sql`](../src/roadgraphtool/SQL/procedures/procedure_compute_speeds_for_segments.sql) and [`procedure_compute_speeds_from_neigborhood_segments.sql`](../src/roadgraphtool/SQL/procedures/procedure_compute_speeds_from_neigborhood_segments.sql) | Every way intersecting the area polygon is used. Car contraction would include footways, and the pedestrian graph would include motorways. |
| One direction per way | `ways.oneway` in [`04_ways.sql`](../src/roadgraphtool/SQL/tables/04_ways.sql) | A street can be one-way for cars and two-way for pedestrians. Only one of them can be stored. The import of the second network fails on the ways with a different direction (`ImportConflictError`). |

The OSM ids are primary keys of `nodes` and `ways`, and `nodes_ways` is unique on `(way_id, position)`. Storing each OSM object once is fine, because its geometry does not depend on the network. Only the network membership and the direction do.


## Proposed changes
1. **Network membership table** `network_ways(area, way_id, oneway)`, primary key `(area, way_id)`, foreign keys to `areas` and `ways`.
    - Both import backends insert one row per imported way, with the direction given by the profile. The direction is then no longer compared with `ways.oneway` when an existing way is reused.
    - `get_ways_in_target_area` joins `network_ways` on `area = target_area_id` and returns its `oneway`. The speed procedures use the same join.
    - `ways.oneway` stays for backward compatibility but is no longer read.
2. **Migration script** creating `network_ways` and filling it from the existing `ways` rows (`area`, `id`, `oneway`), so existing car schemas keep working.
3. **Provenance columns.** `ways.area`, `nodes.area` and `nodes_ways.area` only mean "first imported with this area". The legacy [`procedure_add_temp_map.sql`](../src/roadgraphtool/SQL/procedures/procedure_add_temp_map.sql) deletes by these columns and would delete rows shared with another network; remove the procedure.
4. **Tests.** Update the pgTAP fixtures of the contraction, restricted-node and `get_ways_in_target_area` tests to fill `network_ways`. Add a test that two areas with the same polygon and different way sets produce disjoint edge sets.


## Trade-off
Separate schemas already give consistent ids across networks: node and way ids are OSM ids, exported as `db_id`, unless the input was renumbered with `process_osm.py r`. So a car node and a pedestrian node at the same OSM node can be matched without a shared schema.

A shared schema mainly buys:

- one import of the common nodes and ways instead of two,
- joint SQL queries over both networks without cross-schema joins.

The cost is the table and migration above, edits to the way selection in three SQL functions and procedures and to both import backends, and the test updates. For the Shared stops experiment, separate schemas were chosen.
