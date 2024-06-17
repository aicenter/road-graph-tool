# Python Functions

## Export Functions (export.py)

### `Function : `get_map_nodes_from_db`
This function retrieves map nodes from a database based on the area ID. It utilizes SQLAlchemy for database connectivity and GeoPandas for handling geographic data.

#### Parameters
- `config`: A dictionary containing configuration parameters for database connectivity.
- `server_port`: The port number of the database server.
- `area_id` (int): The ID of the area for which nodes are to be retrieved.

#### Returns
- `gpd.GeoDataFrame`: A GeoDataFrame containing the retrieved map nodes.

# SQL Functions


## `get_area_for_demand`
This function generates a geometric area around specified zones based on certain criteria related to demand.

### Parameters:

- `srid_plain` (integer): The SRID of the plain geometry.
- `dataset_ids` (array of smallint): An array of dataset IDs to filter the demand.
- `zone_types` (array of smallint): An array of zone types to filter.
- `buffer_meters` (integer, default: 1000): The buffer distance in meters around the generated area.
- `min_requests_in_zone` (integer, default: 1): The minimum number of requests in a zone to consider it.
- `datetime_min` (timestamp, default: '2000-01-01 00:00:00'): The minimum datetime for filtering requests.
- `datetime_max` (timestamp, default: '2100-01-01 00:00:00'): The maximum datetime for filtering requests.
- `center_point` (geometry, default: NULL): The center point for filtering zones.
- `max_distance_from_center_point_meters` (integer, default: 10000): The maximum distance in meters from the center point.

### Returns:

- `target_area` (geometry): The generated geometric area around the specified zones.

### Example:

```sql
select *
from get_area_for_demand(
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



## `select_network_nodes_in_area`

### Overview
The `select_network_nodes_in_area` function is designed to retrieve network nodes within a specified geographic area. It returns a table containing information about the nodes such as their index, ID, coordinates, and geometry.

### Parameters
* `area_id`: A small integer representing the ID of the area for which network nodes are to be selected.

### Return Type
The function returns a table with the following columns ordered by id:

* `index`: An integer representing the index of the node.
* `id`: A bigint representing the ID of the node.
* `x`: A double precision value representing the x-coordinate of the node.
* `y`: A double precision value representing the y-coordinate of the node.
* `geom`: A geometry object representing the geometry of the node.

### Example
```SELECT * FROM select_network_nodes_in_area(Cast(5 As smallint));```



# SQL Procedures

## `compute_strong_components`

### Description
The `compute_strong_components.sql` procedure computes strong components for a specified target area and stores the results in the `component_data` table.

### Parameters
- `target_area_id`: A small integer representing area for which strong components are computed.

### Operations
   - **Create Temporary Table**: A temporary table named `components` is created to store the strong components.
   - **Execute Query**: The `pgr_strongcomponents` function is called with a formatted SQL query to compute the strong components based on the target area's geometry and edge data.
   - **Storing Results**: stores the computed strong components in the `component_data` table.
   - **Drop Temporary Table**: The temporary table `components` is dropped to free up memory resources.

### Example
```sql

-- Compute strong components for the target area with ID 5
call compute_strong_components(Cast(5 As smallint));
```
or
```sql
call compute_strong_components(target_area_id := Cast(5 As smallint));
```

![compute_strong_components](https://github.com/aicenter/road-graph-tool/assets/25695606/cf1e0fff-1307-4226-af08-cb1c17d4c3f2)


## `contract_graph_in_area.sql`

### Purpose:

This procedure optimizes road network data within a specific area by contracting the graph representation of the road network and generating optimized edge data.


### Inputs:

* `target_area_id`: A small integer representing the target geographical area ID.
* `target_area_srid`: An integer representing the spatial reference identifier for the target geographical area.


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

* The procedure updates the `nodes` table to mark contracted nodes.
* Edge data for both contracted and non-contracted road segments is inserted into the `edges` table, providing an optimized representation of the road network within the specified geographical area.


### Usage

* Call the procedure with appropriate values for `target_area_id` and `target_area_srid` to process road segment data and optimize the graph representation of the road network.


### Example

```
call public.contract_graph_in_area(Cast(0 As smallint), 0);	
```


or


```
call public.contract_graph_in_area(target_area_id := Cast(0 As smallint), target_area_srid := 0);
```


## `insert_area`
TODO update, now it is not a procedure!

### Description:
This function inserts a new area into a database table named `areas`. The area is defined by its name and a list of coordinates representing its geometry.

### Parameters:
- `name` : The name of the area being inserted (String).
- `coordinates` : A list of coordinates representing the geometry of the area.

### Example :
```sql
insert into areas(name, geom) values('name', st_geomfromgeojson('{"type": "MultiPolygon", "coordinates": []}'))
