# SQL Procedure Manual: compute_strong_components

## Description
The `compute_strong_components.sql` procedure computes strong components for a specified target area and stores the results in the `component_data` table.

## Parameters
- `target_area_id`: A small integer representing area for which strong components are computed.

## Operations
   - **Create Temporary Table**: A temporary table named `components` is created to store the strong components.
   - **Execute Query**: The `pgr_strongcomponents` function is called with a formatted SQL query to compute the strong components based on the target area's geometry and edge data.
   - **Storing Results**: stores the computed strong components in the `component_data` table.
   - **Drop Temporary Table**: The temporary table `components` is dropped to free up memory resources.

## Example
```sql

-- Compute strong components for the target area with ID 5
call compute_strong_components(Cast(5 As smallint));
```
or
```sql
call compute_strong_components(target_area_id := Cast(5 As smallint));
```

![compute_strong_components](https://github.com/aicenter/road-graph-tool/assets/25695606/cf1e0fff-1307-4226-af08-cb1c17d4c3f2)
