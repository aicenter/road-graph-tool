## Procedure: insert_area

### Description:
This function inserts a new area into a database table named `areas`. The area is defined by its name and a list of coordinates representing its geometry.

### Parameters:
- `name` : The name of the area being inserted (String).
- `coordinates` : A list of coordinates representing the geometry of the area.

### Example :
```sql
insert into areas(name, geom) values('name', st_geomfromgeojson('{"type": "MultiPolygon", "coordinates": []}'))
```
