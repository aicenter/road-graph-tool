# Table of Contents

1. [Python Functions](#python-functions)
   1. [Export Functions (export.py)](#export-functions-exportpy)
      - [get_map_nodes_from_db](#get_map_nodes_from_db)

2. [SQL Functions](#sql-functions)
   - [get_area_for_demand](#get_area_for_demand)
   - [get_ways_in_target_area](#get_ways_in_target_area)
   - [insert_area](#insert_area)
   - [select_network_nodes_in_area](#select_network_nodes_in_area)

3. [SQL Procedures](#sql-procedures)
   - [add_temp_map](#add_temp_map)
   - [assign_average_speed_to_all_segments_in_area](#assign_average_speed_to_all_segments_in_area)
   - [compute_speeds_for_segments](#compute_speeds_for_segments)
   - [compute_speeds_from_neighborhood_segments](#compute_speeds_from_neighborhood_segments)
   - [compute_strong_components](#compute_strong_components)
   - [contract_graph_in_area](#contract_graph_in_area)
   - [insert_area](#insert_area)

# Python Functions

## Export Functions (export.py)

### `get_map_nodes_from_db`

#### Description
This function retrieves map nodes from a database based on the area ID.

#### Parameters
- `area_id` (int): The ID of the area for which nodes are to be retrieved.

#### Return Value
- `nodes`: A GeoDataFrame containing the retrieved map nodes.

### `get_map_edges_from_db`

#### Description
This function retrieves map edges from a database based on the area ID and SRID.

#### Parameters
- `config`: A dictionary containing `area_id` and `SRID_plane`.

#### Return Value
- `edges`: A GeoDataFrame containing the retrieved map edges.

## Generation Procedures (instance_generation.py) 

### `generate_dm`

#### Description

This procedure generates a distance matrix for a given set of nodes and edges, which represent a road network.

#### Parameters

- `config` (Dict): A configuration dictionary containing necessary paths and settings.
  - dm_filepath: (Optional) The file path where the distance matrix will be saved.
  - area_dir: Directory path for storing the distance matrix if dm_filepath is not provided.
  - map['path']: Directory path where the map files are located.
- `nodes` (gpd.GeoDataFrame): A GeoDataFrame containing the nodes of the network.
- `edges` (gpd.GeoDataFrame): A GeoDataFrame containing the edges of the network, with optional speed data.
- `allow_zero_length_edges` (bool, default=True): A flag to allow or disallow zero-length edges in the network.

#### Prerequisite

Must be installed [Shortest Distances computation library](https://github.com/aicenter/shortest-distances) (`shortestPathsPreprocessor`)

#### Example

```
from pathlib import Path
from roadgraphtool.distance_matrix_generator import load_instance_config
from roadgraphtool.distance_matrix_generator import generate_dm
from roadgraphtool.map import get_map

config = load_instance_config(Path("C:/Users/sha00/Desktop/config.yaml"))
map_nodes, map_edges = get_map(config)

generate_dm(config, map_nodes, map_edges)
```

# SQL Functions

## [`get_area_for_demand`](SQL/functions/function_get_area_for_demand.sql)

### Description
This function generates a geometric area around specified zones based on certain criteria related to demand.

### Parameters
- `srid_plain` (integer): The SRID of the plain geometry.
- `dataset_ids` (array of smallint): An array of dataset IDs to filter the demand.
- `zone_types` (array of smallint): An array of zone types to filter.
- `buffer_meters` (integer, default: 1000): The buffer distance in meters around the generated area.
- `min_requests_in_zone` (integer, default: 1): The minimum number of requests in a zone to consider it.
- `datetime_min` (timestamp, default: '2000-01-01 00:00:00'): The minimum datetime for filtering requests.
- `datetime_max` (timestamp, default: '2100-01-01 00:00:00'): The maximum datetime for filtering requests.
- `center_point` (geometry, default: NULL): The center point for filtering zones.
- `max_distance_from_center_point_meters` (integer, default: 10000): The maximum distance in meters from the center point.

### Return Value
- `target_area` (geometry): The generated geometric area around the specified zones.

### Example
```sql
SELECT * FROM get_area_for_demand(
    srid_plain := 4326,
    dataset_ids := ARRAY[1, 2, 3]::smallint[],
    zone_types := ARRAY[1, 2, 3]::smallint[],
    buffer_meters := 1000::smallint,
    min_requests_in_zone := 5::smallint,
    datetime_min := '2023-01-01 00:00:00',
    datetime_max := '2023-12-31 23:59:59',
    center_point := st_makepoint(50.0, 10.0),
    max_distance_from_center_point_meters := 5000::smallint
);
```

## [`get_ways_in_target_area`](SQL/functions/function_get_ways_in_target_area.sql)

### Description
This function serves as a helper function to the procedure `assign_average_speed_to_all_segments_in_area()`. Based on the given area identifier, it selects ways that intersect with the geometry of the area.

### Parameters
- `target_area_id` (smallint): Identifier of the area for which intersecting ways are looked up.

### Return Value
Table in the format:

| Column | Type |
|--------|------|
| id | bigint |
| tags | hstore |
| geom | geometry |
| area | integer |
| from | bigint |
| to | bigint |
| oneway | boolean |

### Example
```sql
SELECT * FROM get_ways_in_target_area(18::smallint);
```

## [`insert_area`](SQL/functions/function_insert_area.sql)

### Description

The `insert_area` inserts new area with given geo data in the format of __geojson__.

### Parameters

- `id` (integer): The id of the area (optional).
- `name` (varchar): The name of the area.
- `description` (varchar): The description of the given area (optional).
- `geom` (json): The geometry of the area, should be in geojson format.

### Return Value

This function does not return.

### Example

```sql
-- All parameters
SELECT insert_area(1, 'Area Name', 'Description','{
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [100.0, 0.0],
                    [101.0, 0.0],
                    [101.0, 1.0],
                    [100.0, 1.0],
                    [100.0, 0.0]
                ]
            ],
            [
                [
                    [102.0, 2.0],
                    [103.0, 2.0],
                    [103.0, 3.0],
                    [102.0, 3.0],
                    [102.0, 2.0]
                ]
            ]
        ]
    }');
```

## [`select_network_nodes_in_area`](SQL/functions/function_select_network_nodes_in_area.sql)

### Description
The `select_network_nodes_in_area` function retrieves network nodes within a specified geographic area.

### Parameters
- `area_id` (smallint): The ID of the area for which network nodes are to be selected.

### Return Value
Table with the following columns ordered by id:

| Column | Type | Description |
|--------|------|-------------|
| index | integer | Index of the node |
| id | bigint | ID of the node in table `nodes` |
| x | float | x-coordinate of the node |
| y | float | y-coordinate of the node |
| geom | geometry | Geometry of the node |

### Example
```sql
SELECT * FROM select_network_nodes_in_area(CAST(5 AS smallint));
```

# SQL Procedures

## [`add_temp_map`](SQL/procedures/procedure_add_temp_map.sql)

### Description
This procedure transfers data from temporary tables (with prefix `_tmp`, not SQL `TEMP TABLE`) to permanent tables for a specified map area. It first removes existing data for the given area from permanent tables, then inserts new data from corresponding temporary tables.

### Parameters
- `map_area` (integer): The identifier of the map area for which data is being added or updated.

### Operations
1. Delete existing data for the specified `map_area` from permanent tables:
   - `ways`
   - `nodes`
   - `nodes_ways`
2. Insert new data from temporary tables to permanent tables:
   - Insert into `nodes` from `nodes_tmp`
   - Insert into `ways` from `ways_tmp`, joining with `nodes_tmp`
   - Insert into `nodes_ways` from `nodes_ways_tmp`, joining with `ways_tmp` and `nodes_tmp`

### Notes
- All insert operations use `ON CONFLICT DO NOTHING` clause to handle potential conflicts.
- The procedure assumes that temporary tables contain only data related to the specified `map_area`.

### Example
```sql
CALL add_temp_map(5);
```
or
```sql
CALL add_temp_map(map_area := 5);
```

## [`assign_average_speed_to_all_segments_in_area`](SQL/procedures/procedure_assign_average_speed_to_all_segments_in_area.sql)

### Description
This procedure assigns average speed to all segments in a specified area. It calculates the average speed and standard deviation from existing data, then applies these values to segments within the target area.

### Parameters
- `target_area_id` (smallint): The identifier of the target area.
- `target_area_srid` (integer): The Spatial Reference System Identifier for the target area.

### Operations
1. Calculate average speed and standard deviation from `nodes_ways_speeds` table where quality is 1 or 2.
2. Identify target ways using `get_ways_in_target_area` function.
3. Generate node segments for the target area.
4. Insert new records into `nodes_ways_speeds` table with calculated average speed, standard deviation, and quality 5.

### CTEs (Common Table Expressions)
1. `average_speed`: Calculates average speed and standard deviation.
2. `target_ways`: Retrieves ways in the target area.
3. `node_segments`: Generates node segments for the target area.

### Notes
- The procedure uses `ON CONFLICT DO NOTHING` to handle potential conflicts during insertion.
- It assigns a quality of 5 to newly inserted records.
- The procedure raises notices about the progress of the operation.

### Example
```sql
CALL assign_average_speed_to_all_segments_in_area(1, 4326);
```

### Error Handling
- The procedure throws exceptions for invalid area IDs and when the `nodes_ways_speeds` table is empty before execution.

Here's what should be added to the reference.md file based on the provided procedure description:

## [`compute_speeds_for_segments`](SQL/procedures/procedure_compute_speeds_for_segments.sql)

### Description
Calculates speeds for a given hour and day of the week within a specified target area.

### Input Parameters
- `target_area_id` (smallint): Identifier for the target area.
- `speeds_records_dataset` (smallint): Identifier for the speed records dataset.
- `hour` (smallint): The hour for which the speeds are being computed.
- `day_of_week` (smallint): The day of the week for which the speeds are being computed (optional).

### Returns
This procedure does not return any values.

### Operations

1. Create temporary tables:
   - `target_ways`: Contains ways in the target area.
   - `node_sequences`: Contains records indicating from which node to which node one can travel via a specific way.

2. Determine dataset quality:
   - If `day_of_week` is not provided, set `dataset_quality = 2`.
   - Otherwise, set `dataset_quality = 1`.

3. Create temporary table `grouped_speed_records`:
   - If `dataset_quality = 1`, source data from `speed_records`.
   - If `dataset_quality = 2`, source data from `speed_records_quarterly`.

4. Insert data into `nodes_ways_speeds`:
   - Merge data selection into two groups: ascending sequences and descending sequences.
   - Insert the merged data into `nodes_ways_speeds`.

### Notes
- The procedure uses temporary tables and indexes for optimal performance.
- It processes data differently based on whether a specific day of the week is provided or not.

## [`compute_speeds_from_neighborhood_segments`](SQL/procedures/procedure_compute_speeds_from_neigborhood_segments.sql)

### Description
This procedure computes speeds for road segments within a specified target area using nearby segments' speed data and overall average speeds. It assigns speeds to segments in the `nodes_ways_speeds` table based on proximity and overall averages.

### Parameters
- `target_area_id` (smallint): Identifier for the target area.
- `target_area_srid` (integer): Spatial reference system identifier for the target area.

### Operations
1. Create materialized view `target_ways` for roads within the specified area.
2. Create materialized view `node_segments` for segments between nodes in target ways, excluding segments with assigned speeds.
3. Create temporary table `speed_segment_data` with geometric representation of segments, speeds, and standard deviations.
4. Assign speeds to segments within 10 meters, setting quality to 3.
5. Assign speeds to segments within 200 meters, setting quality to 4.
6. Calculate overall average speed and standard deviation.
7. Assign overall average speed to remaining segments, setting quality to 5.
8. Clean up temporary objects.

### Notes
- The procedure uses spatial operations and joins to compute and assign speeds.
- Speed assignments are done in stages, with increasing distance thresholds and decreasing quality values.
- Temporary views and tables are used for efficient data manipulation.

### Example
```sql
CALL compute_speeds_from_neighborhood_segments(1, 4326);
```
or
```sql
CALL compute_speeds_from_neighborhood_segments(
    target_area_id := 1,
    target_area_srid := 4326
);
```

### Error Handling
- The procedure may throw an error if invalid or null values are passed for `target_area_id` or `target_area_srid`.
- No new entries will be added to the target table if required data is missing from related tables (`areas`, `nodes`, `nodes_ways`).

## [`compute_strong_components`](SQL/procedures/procedure_compute_strongly_connected_components.sql)

### Description
The `compute_strong_components` procedure computes strong components for a specified target area and stores the results in the `component_data` table.

### Parameters
- `target_area_id` (smallint): Area for which strong components are computed.

### Operations
1. Create temporary table `components` to store strong components.
2. Execute `pgr_strongcomponents` function to compute strong components.
3. Store results in the `component_data` table.
4. Drop temporary table `components`.

### Example
```sql
CALL compute_strong_components(CAST(5 AS smallint));
```
or
```sql
CALL compute_strong_components(target_area_id := CAST(5 AS smallint));
```

![compute_strong_components](https://github.com/aicenter/road-graph-tool/assets/25695606/cf1e0fff-1307-4226-af08-cb1c17d4c3f2)

## [`contract_graph_in_area`](SQL/procedures/procedure_contract_graph_in_area.sql)

### Description
This procedure optimizes road network data within a specific area by contracting the graph representation of the road network and generating optimized edge data.

### Parameters
- `target_area_id` (smallint): The target geographical area ID.
- `target_area_srid` (integer): The spatial reference identifier for the target geographical area.

### Operations
1. Create Temporary Table `road_segments`:
    * This operation selects road segment data within the specified geographical area using the `select_node_segments_in_area` function and creates a temporary table named `road_segments`.
    * The road segments are filtered based on the `target_area_id` and `target_area_srid` parameters.
    * An index named `road_segments_index_from_to` is created on the `from_id` and `to_id` columns of the `road_segments` table to optimize query performance.
2. Contract Graph:
    * This operation contracts the graph representation of the road network using the `pgr_contraction` function.
    * The contracted vertices are stored in a temporary table named `contractions`, along with their corresponding source and target nodes.
    * Another index named `contractions_index_contracted_vertex` is created on the `contracted_vertex` column of the `contractions` table for efficient retrieval of contracted vertices.
3. Update Nodes:
    * This operation updates the `nodes` table, marking nodes as contracted where their IDs match the contracted vertices stored in the `contractions` table.
4. Create Edges for Non-contracted Road Segments:
    * This operation generates edge data for non-contracted road segments by joining the `road_segments` table with the `nodes` table to retrieve geometry and other attributes.
    * The resulting edge data is inserted into the `edges` table, which represents the road network.
5. Generate Contraction Segments:
    * This operation generates contraction segments based on the contracted graph representation stored in the `contractions` table.
    * Contraction segments represent aggregated road segments between contracted nodes.
    * The generated segments are stored in a temporary table named `contraction_segments`.
6. Create Edges for Contracted Road Segments:
    * This operation generates edge data for contracted road segments by aggregating contraction segments and calculating average speed.
    * The resulting edge data is inserted into the `edges` table, complementing the existing edge data for non-contracted segments.

![procedure_contract_graph_in_area](https://github.com/aicenter/road-graph-tool/assets/25695606/8de0fd29-6500-4a13-a3c1-31b57f864c65)

### Outputs
- Updates `nodes` table to mark contracted nodes.
- Inserts edge data for both contracted and non-contracted road segments into the `edges` table.

### Example
```sql
CALL public.contract_graph_in_area(CAST(0 AS smallint), 0);
```
or
```sql
CALL public.contract_graph_in_area(target_area_id := CAST(0 AS smallint), target_area_srid := 0);
```

## [`insert_area`](SQL/insert_area.sql)
TODO update, now it is not a procedure!

### Description
This function inserts a new area into a database table named `areas`. The area is defined by its name and a list of coordinates representing its geometry.

### Parameters

- `name` (string): The name of the area being inserted.
- `coordinates` (list): A list of coordinates representing the geometry of the area.

### Example
```sql
INSERT INTO areas(name, geom) VALUES('name', st_geomfromgeojson('{"type": "MultiPolygon", "coordinates": []}'));
```
