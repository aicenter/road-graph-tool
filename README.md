The Road Graph Tool is a Project for processing data from various sources into a road graph data usable as an input for transportation problems. Version 1.0.0 of the project targets to provide a road network with the following features:
- geographical location of vertices and edges,
- geographical shape of edges,
- elevation of vertices,
- measured and posted speed of edges, and
- travel demand data located at the vertices.

The version 1.0.0 of use the following data sources:
- OpenStreetMap (OSM) data for the road network and its geographical properties,
- SRTM data for the elevation of vertices,
- Uber Movement data for the speed of edges.
- Travel demand data from various sources.

The processing and storage of the data are done in a PostgreSQL/PostGIS database. To manipulate the database, import data to the database, and export data from the database, the project provides a set of Python scripts. 

# Quick Start Guide

To run the tool, you need access to a local or remote PostgreSQL database with the PostGIS, PgRouting, and hstore (available by default) extensions installed. The remote database can be accessed through an SSH tunnel. The SSH tunneling is handled at the application level; you only need to provide the necessary configuration in the `config.ini` file (see the [config-EXAMPLE.ini](./config-EXAMPLE.ini) file for an example configuration).

After setting up the configuration file, your next step is to edit the `main.py` file to execute only the steps you need. Currently, the content of `main.py` includes Python wrappers for the provided SQL functions in the `SQL/` directory, an example of an argument parser, and a main execution pipeline, which may be of interest to you.

To execute the configured pipeline, follow these steps:

1. In the `python/` directory, run `py scripts/install_sql.py`. If some of the necessary extensions are not available in your database, the execution will fail with a corresponding logging message. Additionally, this script will initialize the needed tables, procedures, functions, etc., in your database.

2. Next, you should import OSM data into your database. Follow the steps in [importer/README.md](./importer/README.md) to import data from your `.pbf` file.

3. Importing with the tool [osm2pgsql](https://osm2pgsql.org/) can be quite tricky, which necessitates post-processing the schema of your database. If you imported the `.pbf` file with the style [pipeline.lua](./importer/styles/pipeline.lua), you will need to execute the file `SQL/after_import.sql`.

4. Your database is now ready. You can execute [main.py](./python/scripts/main.py) in the `python/` directory.

So in the end execution order may look like this:
```sh
alias py=python3
cd python/
echo 'Pre-processing database...'
py scripts/install_sql.py
cd ../importer/
echo 'Importing with osm2pgsql...'
osm2pgsql -d DATABASE_NAME -P 5432 -U USERNAME -x -S styles/pipeline.lua --output=flex COUNTRY.osm.pbf
echo 'Post-processing database...'
psql -d DATABASE_NAME -U USERNAME -f ../SQL/after_import.sql
cd ../python/
echo 'Executing main.py...'
py main.py -a 1 -s 4326 -f False
```

# Testing
For testing the PostgreSQL procedures that are the core of the Road Graph Tool, we use the [pgTAP testing framework](https://github.com/theory/pgtap). To learn how to use pgTAP, see the [pgTAP manual](./doc/pgtap.md).


To run the tests, follow these steps:
1. Install the `pgTAP` extension for your PostgreSQL database cluster according to the [pgTAP manual](./doc/pgtap.md).
1. If you haven't already, create and initialize the database
    1. create new database using `CREATE DATABASE <database_name>;`
    1. copy the `config-EXAMPLE.ini` file to `config.ini` and fill in the necessary information
    1. inititalize new database using the script `<rgt root>/python/scripts/install_db.py`. 
        - this script will install all necessary extensions and create all necessary tables, procedures, and functions.
        - the configuration for the database is loaded from the `config.ini` file.
4. Execute the tests by running the following query in your PostgreSQL console:
    ```sql
    SELECT * FROM run_all_tests();
    ```
    - This query will return a result set containing the execution status of each test.

# Components
The road graph tool consists of a set of components that are responsible for individual processing steps, importing data, or exporting data. Each component is implemented as an PostgreSQL procedure, possibly calling other procedures or functions. Additionally, each component has its own Python wrapper script that connects to the database and calls the procedure. Currently, the following components are implemented:
- **Graph Contraction**: simplifies the road graph by contracting nodes and creating edges between the contracted nodes.

## Graph Contraction 
This script contracts the road graph within a specified area. 

- function: `contract_graph_in_area`
- SQL procedure: `contract_graph_in_area`
- location: `python/main.py`
- required tables:
    - `nodes`
    - `edges`
    - `road_segments`


### Processing details
The SQL procedure `contract_graph_in_area` processes the graph in the following steps, visualized in the diagram below:

1. **Road Segments Table Creation**: Generates a temporary table containing road segments within a target area. A road segment is a line between two subsequent nodes from the OSM data.
1. **Graph Contraction**: Contracts the graph by creating a temporary table that holds the contraction information for each node.
1. **Node Updates**: Updates the nodes in the database to mark some of them as contracted.
1. **Edge Creation**: Generates edges for both contracted and non-contracted road segments.
1. **Contraction Segments Generation**: Creates contraction segments to facilitate the creation of edges for contracted road segments.


![procedure_contract_graph_in_area](https://github.com/aicenter/road-graph-tool/assets/25695606/8de0fd29-6500-4a13-a3c1-31b57f864c65)






