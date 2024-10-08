The Road Graph Tool is a project for processing data from various sources into a road graph usable as an input for transportation problems. Version 0.1.0 of the project targets to provide a road network with the following features:

- geographical location of vertices and edges, and
- geographical shape of edges

The version 0.1.0 use the following data sources:

- OpenStreetMap (OSM) data for the road network and its geographical properties,

The processing and storage of the data are done in a PostgreSQL/PostGIS database. To manipulate the database, import data to the database, and export data from the database, the project provides a set of Python scripts.


# Dependencies
To run the tool, you need access to a local or remote PostgreSQL database with the following extensions installed:

- [PostGIS](https://postgis.net/)
- [PgRouting](https://pgrouting.org/), and
- hstore (available by default).

Refer to the [Prerequisities](#prerequisities) section for details on installing the required dependencies for importing data into the database.

# Quick Start Guide
After setting up the configuration file, your next step is to edit the `main.py` file to execute only the steps you need. Currently, the content of `main.py` includes Python wrappers for the provided SQL functions in the `SQL/` directory, an example of an argument parser, and a main execution pipeline, which may be of interest to you.

To execute the configured pipeline, follow these steps:

1. Install the Road Graph Tool Python package: `pip install -e <clone dir>/Python`.
1. Configure the database in the `config.ini` file (see the [config-EXAMPLE.ini](./config-EXAMPLE.ini) file for an example configuration). The remote database can be accessed through an SSH tunnel. The SSH tunneling is handled at the application level.
1. In the `python/` directory, run `py scripts/install_sql.py`. If some of the necessary extensions are not available in your database, the execution will fail with a corresponding logging message. Additionally, this script will initialize the needed tables, procedures, functions, etc., in your database.

2. Next, you should import OSM data into your database - this project utilizes [osm2pgsql](https://osm2pgsql.org/) for that.

    > **_NOTE:_** Tool _osm2pgsql_ uses connection to database specified in `config.ini` file, so make sure to check that the connection details are correct and that the database server is running.
    If the server database requires password, store it to your home directory in `.pgpass` (Ubuntu/MacOS, [Windows](https://www.postgresql.org/docs/current/libpq-pgpass.html)) file in following format: `hostname:port:database:username:password`.

    To start importing, run the `main.py` script with with `-i` or `--import`flag. This triggers [import_osm_to_db()](python/scripts/process_osm.py) function, which requires the OSM file path as an argument. 
    > **_NOTE:_** To ensure the SSH tunnel is correctly set up for a remote database, provide `ssh` details in [config-EXAMPLE.ini](./config-EXAMPLE.ini). SSH tunnel setup is handled with [set_ssh_to_db_server_and_set_port()](python/roadgraphtool/db.py).
    
    A style file path can also be provided - if omitted, the default style file [default.lua](resources/lua_styles/default.lua) is used. To customize the style file, define a new path for the [DEFAULT_STYLE_FILE](python/scripts/process_osm.py).

    For more detailed information on importing OSM data into the database, please refer to the [OSM file processing section](#osm-file-processing).

    > **_NOTE:_** Alternatively, you can upload OSM data by executing `py scripts/process_osm.py u COUNTRY.osm.pbf` - for further details, see [Section 2 of **OSM file processing and importing**](#2-importing-to-database-using-flex-output)

3. Importing with the tool [osm2pgsql](https://osm2pgsql.org/) can be quite tricky, which necessitates post-processing the schema of your database. If you imported the `.pbf` file with the style [pipeline.lua](resources/lua_styles/pipeline.lua), you will need to execute the file `SQL/after_import.sql`.

4. Your database is now ready. You can execute [main.py](./python/scripts/main.py) in the `python/` directory.

So in the end execution order may look like this:
```sh
alias py=python3
cd python/
echo 'Pre-processing database...'
py scripts/install_sql.py
echo "Importing OSM data to database"
py scripts/process_osm.py u COUNTRY.osm.pbf
"Begin importing with: 'osm2pgsql -d DATABASE_NAME -P 5432 -U USERNAME -x -S styles/pipeline.lua --output=flex COUNTRY.osm.pbf' ..."
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
The road graph tool consists of a set of components that are responsible for individual processing steps, importing data, or exporting data. Each component is implemented as an PostgreSQL procedure or Python script, possibly calling other procedures or functions. Additionally, each component has its own Python wrapper script that connects to the database and calls the procedure. Currently, the following components are implemented:
- **OSM file processing for importing to PostgreSQL database**: processes data from OSM file that are to be imported into PostgreSQL database for further use
- **Graph Contraction**: simplifies the road graph by contracting nodes and creating edges between the contracted nodes.

## OSM file processing and importing
### Prerequisities
Before processing and loading data (can be downloaded at [Geofabrik](https://download.geofabrik.de/)) into the database, we'll need to install several libraries: 
* psql (for PostgreSQL)
* osmium: osmium-tool (macOS: `brew install osmium-tool`, Ubuntu: `apt install osmium-tool`)
* osm2pgsql (macOS: `brew install osm2pgsql`, Ubuntu: `apt install osm2pgsql` for version 1.6.0) - the current version of RGT is currently compatible with both `2.0.0` and `1.11.0` versions of `osm2pgsql`.
The PostgreSQL database needs PostGis extension in order to enable spatial and geographic capabilities within the database, which is essential for working with OSM data.
Loading large OSM files to database is memory demanding so [documentation](https://osm2pgsql.org/doc/manual.html#system-requirements) suggests to have RAM of at least the size of the OSM file.

### 1. Preprocessing of OSM file (optional)
Preprocessing an OSM file with osmium aims to enhance importing efficiency and speed of osm2pgsql tool. The two most common actions are sorting and renumbering. For these options, you can use the provided `process_osm.py` Python script:
```bash
python3 process_osm.py [option_flag] [input_file] -o [output_file]
```
Call `python3 process_osm.py -h` or `python3 process_osm.py --help` for more information.

- Sorting: Sorts objects based on IDs in ascending order.
```bash
python3 process_osm.py s [input_file] -o [output_file]
```
- Renumbering: Negative IDs usually represent inofficial non-OSM data (no clashes with OSM data), osm2pgsql can only handle positive sorted IDs (negative IDs are used internally for geometries).
Renumbering starts at index 1 and goes in ascending order.
```bash
python3 process_osm.py s [input_file] -o [output_file]
```
- Sorting and renumbering: Sorts and renumbers IDs in ascending order starting from index 1.
```bash
python3 process_osm.py sr [input_file] -o [output_file]
```

### 2. Importing to database using Flex output
The primary function of  `process_osm.py` script is to import OSM data to the database using [osm2pgsql](https://osm2pgsql.org) tool configured by [Flex output](https://osm2pgsql.org/doc/manual.html#the-flex-output). Flex output allows more flexible configuration such as filtering logic and creating additional types (e.g. areas, boundary, multipolygons) and tables for various POIs (e.g. restaurants, themeparks) to get the desired output. To use it, we define the Flex style file (Lua script) that has all the logic for processing data in OSM file.

The default style file for this project is `resources/lua_styles/default.lua`, which processes and all nodes, ways and relations without creating additional attributes (based on tags) into following tables: `nodes` (node_id, geom, tags), `ways` (way_id, geom, tags, nodes), `relations` (relation_id, tags, members).

Use `u` flag to upload data into database.
```bash
python3 process_osm.py u [input_file] [-l style_file]
```
> **_WARNING:_** Running this command will overwrite existing data in the relevant table (these tables are specified in [schema.py](python/roadgraphtool/schema.py)). If you wish to proceed, use `--force` flag to overwrite or create new schema for new data.

E.g. this command (described bellow) processes OSM file of Lithuania using Flex output and uploads it into database (all configurations should be provided in `config.ini` in top folder).
```bash
# runs with default.lua
python3 process_osm.py u lithuania-latest.osm.pbf
# runs with highway.lua script
python3 process_osm.py u lithuania-latest.osm.pbf -l resources/lua_styles/highway.lua
```

**Nodes in Lithuania:**

![Nodes in Lithuania in QGIS](doc/images/default-nodes.png)

It should be noted that `process_osm.py u` and `process_osm.py b` both run osm2pgsql with `-x` flag (extra attributes) which adds OSM attributes such as version, timestamp, uid, etc. to the OSM objects processed in osm2pgsql since normally objects without tags would not be processed.

### 3. Filtering and extraction
Data are often huge and lot of times we only need certain extracts or objects of interest in our database. So it's better practice to filter out only what we need and work with that in our database.

#### 3.1 Geographical extracts

#### 3.1.1 Box boundary extracts
Both osmium and osm2pgsql filter data inside the bounding box of following format: `bottom-left (minlon,minlat) corner, top-right (maxlon,maxlat) corner`.

**Nodes inside bounding box in Lithuania:**

![Nodes inside bounding box in Lithuania in QGIS](doc/images/bb-nodes.png)

##### Osmium
- These commands process OSM file using bounding box coordinates to filter data within the bounding box. File `resources/extracted-bbox.osm.pbf` is created and can be futher processed with Flex output.
```bash
# bounding box specified directly
python3 filter_osm.py b [input_file] -c [left],[bottom],[right],[top]
# bounding box specified in config file:
python3 filter_osm.py b [input_file] -c [config_file]
```
- E.g. extract bounding box of Lithuania OSM file:
```bash
python3 filter_osm.py b lithuania-latest.osm.pbf -c 25.12,54.57,25.43,54.75
# or:
python3 filter_osm.py b lithuania-latest.osm.pbf -c resources/extract-bbox.geojson
```

##### Flex output
- We can calculate the greatest bounding box coordinates using `python3 process_osm.py b` based on the ID of relation (mentioned in [3.1.2](#312-multipolygon-id-extracts)) that specifies the area of interest (e.g. Vilnius - capital of Lithuania). This command processes OSM file using calculated bounding box coordinates with Flex output and imports the bounded data into database.
```bash
# find bbox (uses Python script find_bbox.py)
python3 process_osm.py b [input_file] -id [relation_id] -s [style_file]
```

- E.g. this command extracts greatest bounding box from given relation ID of Lithuania OSM file and uploads it to PostgreSQL database using osm2pgsql:
```bash
python3 process_osm.py b lithuania-latest.osm.pbf -id 1529146
```

#### 3.1.2 Multipolygon ID extracts
For more precise extraction, we define multipolygon - its specification is based on relation ID: https://www.openstreetmap.org/api/0.6/relation/RELATION-ID/full.

It's better to filter out only what we need with osmium (before processing with flex output) [as suggested](https://osm2pgsql.org/examples/road-length/).

**Ways inside multipolygon of Vilnius:**

![Ways inside multipolygon of Vilnius in QGIS](doc/images/multi-ways.png)

##### Osmium
- ID can be found by specific filtering using `resources/expression-example.txt` or on OpenStreetMap - [more on how to filter](#32-filter-tags)
    - note: `admin_level=*` expression represents administrative level of feature (borders of territorial political entities) - each country (even county) can have different numbering
    - use `name:en` for easiest filtering
- e.g. to find relation ID that bounds Vilnius city (ID: 1529146), run double [tag filtration](#32-filter-tags):
```bash
# expressions-example.txt should contain: r/type=boundary
python3 filter_osm.py f lithuania-latest.osm.pbf -e expressions-example.txt
# expressions-example.txt should contain: r/name:en=Vilnius
python3 filter_osm.py f lithuania-latest.osm.pbf -e expressions-example.txt
```
- get multipolygon extract that can be further processed with Flex output:
```bash
python3 filter_osm.py id [input_file] -rid [relation_id] [-s strategy] 
# E.g. extract multipolygon based on relation ID of Vilnius city:
python3 filter_osm.py id lithuania-latest.osm.pbf -rid 1529146 # creates: id_extract.osm
python3 process_osm.py u id_extract.osm
```
- Strategies (optional for `id` and `b` flags in `filter_osm.py`) are used to extract region in certain way: use `[-s strategy]`to set strategy:
    - simple: faster, doesn't include complete ways (ways out of multipolygon)
    - complete ways: ways are reference-complete
    - smart: ways and multipolygon relations (by default) are reference-complete

#### 3.2 Filter tags
Filter specific objects based on tags.
- common tags: 
	- amenity, building, highway, leisure, natural, boundary
	- [find more tags here](https://wiki.openstreetmap.org/wiki/Main_Page)

**Ways with highway tag in Lithuania:**

![Ways with highway tag in Lithuania in QGIS](doc/images/highway-ways.png)

#### 3.2.1 Osmium
<!-- https://osmcode.org/osmium-tool/manual.html#filtering-by-tags -->
* use `resources/expressions-example.txt` to specify tags to be filtered in format: `[object_type]/[expression]` where:
    * `object_type`: n (nodes), w (ways), r (relations) - can be combined
    * `expression`: what it should match against
```bash
python3 filter_osm.py t [input_file] -e [expression_file] [-R]
```
- Optional `-R` flag: nodes referenced in ways and members referenced in relations will not be added to output if `-R` flag is used
#### 3.2.2 Flex output
- Use lua style files to filter out desired objects.
    - e.g.`resources/lua_styles/filter-highway.lua` filters nodes, ways and relations with highway tag
```bash
python3 process_osm.py u lithuania-latest.osm.pbf -s resources/lua_styles/filter-highway.lua
```
- More examples of various Flex configurations can be found in the oficial [osm2pgsql GitHub project](https://github.com/osm2pgsql-dev/osm2pgsql/tree/master/flex-config).

### Logging
Both `filter_osm.py` and `process_osm.py` output some basic logging info. Use `-v/--verbose` for more debugging.

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


![procedure_contract_graph_in_area](https://github.com/user-attachments/assets/6a4b7c8d-6a95-4c75-836c-2e1a4622575a)




