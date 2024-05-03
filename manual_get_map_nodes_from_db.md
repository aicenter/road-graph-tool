## Function : get_map_nodes_from_db

This function retrieves map nodes from a database based on the area ID. It utilizes SQLAlchemy for database connectivity and GeoPandas for handling geographic data.

## Parameters
- `config`: A dictionary containing configuration parameters for database connectivity.
- `server_port`: The port number of the database server.
- `area_id` (int): The ID of the area for which nodes are to be retrieved.

## Returns
- `gpd.GeoDataFrame`: A GeoDataFrame containing the retrieved map nodes.
