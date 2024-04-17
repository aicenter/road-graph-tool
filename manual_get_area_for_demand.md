## Function: get_area_for_demand

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
