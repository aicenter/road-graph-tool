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

Also, you need the [osm2pgsql](https://osm2pgsql.org/) tool installed for importing OSM data into the database.


# Quick Start Guide
To execute the configured pipeline, follow these steps:

1. Install the Road Graph Tool Python package: `pip install -e <clone dir>/Python`.
1. Create a YAML configuration file for the project. For details about this file, refer to the [Configuration](#configuration) section.
    1. Configure the database. The remote database can be accessed through an SSH tunnel. The SSH tunneling is handled at the application level.
1. In the `python/` directory, run the `scripts/install_sql.py`. This script will initialize the needed tables, procedures, functions, etc., in your database.
1. Run the `main.py` script with with the path to the configuration file as the first argument. The script will execute the pipeline according to the configuration file.


# Configuration
For configuring the Road Graph Tool, we use the [YAML](https://yaml.org/) format. The path to the configuration file should be specified as a first argument when running the main script.

All the relative paths specified in the configuration file are relative to the configuration file itself, unless specified otherwise.

The main configuration affecting the whole tool is in the root of the configuration file. Other parameters are in following sections:

- `db`: database configuration
- `importer`: configuration for the import component
- `export`: configuration for the export component
- `contraction`: configuration for the contraction component
- `strong_components`: configuration for the strong component which filters out the isolated vertices from the graph

Each component configuration has a property `activated` that activates the component if set to `true` and deactivates it if set to `false`.

In the root of the project, there is an example configuration file named `config-example.yml`.

## Password configuration
Additionaly, it is necessary to store some sensitive information like passwords. These are stored in the `secrets.yml` file, that should be stored in the same directory as the configuration file. The structure of the file is the same as the structure of the main configuration file. The example file is stored in the root of the project and is named `secrets-example.yml`.


# Testing
For testing the PostgreSQL procedures that are the core of the Road Graph Tool, we use the [pgTAP testing framework](https://github.com/theory/pgtap). To learn how to use pgTAP, see the [pgTAP manual](https://f-i-d-o.github.io/Manuals/Programming/Database/PostgreSQL%20Manual/#testing-with-pgtap).


To run the tests, follow these steps:

1. Install the `pgTAP` extension for your PostgreSQL database cluster according to the [pgTAP manual](https://f-i-d-o.github.io/Manuals/Programming/Database/PostgreSQL%20Manual/#installation).
1. If you haven't already, create and initialize the database
1. Install the `pgTAP` extension in the database by running the following command in your PostgreSQL console:
    ```sql
    CREATE EXTENSION pgtap WITH SCHEMA public;
    ```
1. Execute the tests by running the following query in your PostgreSQL console:
    ```sql
    SELECT * FROM run_all_tests();
    ```
    - This query will return a result set containing the execution status of each test.

To run just a selection of tests, use the following query:
```sql
SELECT * FROM mob_group_runtests('_insert_area_.*');
```
This query will run all tests that match the regular expression `_insert_area_.*`, and also the fixtures that match the same regular expression.


# Filtration of the input data
Because the map processing with Road Graph Tool can be time-consuming, it is recommended to filter the input data before processing. Most importantly, the data should be filtered to include

- only the area of interest, and
- only the objects of interest.

The following tools are available for filtering the input data:

- [Osmium](https://osmcode.org/osmium-tool/manual.html)
- [Osmfilter](https://wiki.openstreetmap.org/wiki/Osmfilter)



# Components
The road graph tool consists of a set of components that are responsible for individual processing steps, importing data, or exporting data. Each component is implemented as an PostgreSQL procedure or Python script, possibly calling other procedures or functions. Additionally, each component has its own Python wrapper script that connects to the database and calls the procedure. Currently, the following components are implemented:
- **OSM file processing for importing to PostgreSQL database**: processes data from OSM file that are to be imported into PostgreSQL database for further use
- **Graph Contraction**: simplifies the road graph by contracting nodes and creating edges between the contracted nodes.

## OSM file processing and importing
This component processes the data in an [Open Street Map (OSM) XML file format](https://wiki.openstreetmap.org/wiki/OSM_XML) and imports it into a PostgreSQL database. 

### Prerequisities
Before processing and loading data (can be downloaded at [Geofabrik](https://download.geofabrik.de/)) into the database, we'll need to install several libraries: 
* [psql](https://www.postgresql.org/) for PostgreSQL
* [osmium](https://osmcode.org/): osmium-tool (macOS: `brew install osmium-tool`, Ubuntu: `apt install osmium-tool`) for preprocessing of OSM files
* [osm2pgsql](https://osm2pgsql.org/) (macOS: `brew install osm2pgsql`, Ubuntu: `apt install osm2pgsql` for version 1.6.0) for importing - the current version of RGT is compatible with both `2.0.0` and `1.11.0` version of `osm2pgsql`.
The PostgreSQL database needs PostGis extension in order to enable spatial and geographic capabilities within the database, which is essential for working with OSM data.
Loading large OSM files to database is memory demanding so [documentation](https://osm2pgsql.org/doc/manual.html#system-requirements) suggests to have RAM of at least the size of the OSM file.

### 1. Preprocessing of OSM file
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
python3 process_osm.py r [input_file] -o [output_file]
```
- Sorting and renumbering: Sorts and renumbers IDs in ascending order starting from index 1.
```bash
python3 process_osm.py sr [input_file] -o [output_file]
```

### 2. Importing to database using Flex output
The primary function of  `process_osm.py` script is to import OSM data to the database using `osm2pgsql` tool configured by [Flex output](https://osm2pgsql.org/doc/manual.html#the-flex-output). Flex output allows more flexible configuration such as filtering logic and creating additional types (e.g. areas, boundary, multipolygons) and tables for various POIs (e.g. restaurants, themeparks) to get the desired output. To use it, we define the Flex style file (Lua script) that has all the logic for processing data in OSM file.

The `u` flag triggers [import_osm_to_db()](#function-import_osm_to_db) function, which requires the OSM file path as an argument. 

#### Function [import_osm_to_db()](python/roadgraphtool/process_osm.py):
- **Imports** the data into the database (default schema is `public, but a different schema can be specified) with provided Lua *style file* - if omitted, the default style file [pipeline.lua](lua_styles/pipeline.lua) is used. To customize the style file, set a new path for the [DEFAULT_STYLE_FILE](python/roadgraphtool/process_osm.py).
- **Postprocesses** the data in database if specified in [POSTPROCESS_DICT](python/roadgraphtool/process_osm.py), which can be configured based on the *style file* used during importing

```bash
python3 process_osm.py u [input_file] [-sf style_file]
```
> **_WARNING:_** Running this command **will overwrite** existing data in the relevant table (these tables are specified in [schema.py](python/roadgraphtool/schema.py)). If you wish to proceed, use `--force` flag to overwrite or create new schema for new data.

E.g. this command (described bellow) processes OSM file of Lithuania using Flex output and uploads it into database (all configurations should be provided in `config.ini` in root folder of the project).
```bash
# runs with pipeline.lua
python3 process_osm.py u lithuania-latest.osm.pbf
# runs with simple.lua script
python3 process_osm.py u lithuania-latest.osm.pbf -sf resources/lua_styles/simple.lua
```

**Nodes in Lithuania:**

![Nodes in Lithuania in QGIS](doc/images/default-nodes.png)

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
    - use `name:en` for easiest filtering
    > **_NOTE:_** `admin_level=*` expression represents administrative level of feature (borders of territorial political entities) - each country (even county) can have different numbering
    
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
    * [more details](https://docs.osmcode.org/osmium/latest/osmium-tags-filter.html)
```bash
python3 filter_osm.py t [input_file] -e [expression_file] [-R]
```
- Optional `-R` flag: nodes referenced in ways and members referenced in relations will not be added to output if `-R` flag is used
- e.g. to filter out highway objects use:
```bash
# expression file contains: nwr/highway
python3 filter_osm.py t [input_file] -e [expression_file]
```
* use `filter_osm.py h` to filter objects with highway tags (even referenced and untagged)

#### 3.2.2 Flex output
- Use lua style files to filter out objects that have the **desired tag**.
    - e.g. to filter out highway objects use `resources/lua_styles/filter-highway.lua` which filters nodes, ways and relations with **highway** flag
```bash
python3 process_osm.py u lithuania-latest.osm.pbf -s resources/lua_styles/filter-highway.lua
```
> **_NOTE:_** Unfortunately, **untagged** nodes and members **referenced** in ways and relations respectively can't be included as `osm2pgsql` processes objects in [certain order](https://osm2pgsql.org/doc/manual.html#the-after-callback-functions). Use `filter_osm.py` for filtering referenced objects too.

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

## Exporter
The exporter component is responsible for exporting the processed data from the database. Currently, the following formats are supported:

- **CSV**: exports the data to two CSV files: one for nodes and one for edges. The columns are separated by a tabulator.
- **Shapefile**: exports the data to two [shapefiles](https://en.wikipedia.org/wiki/Shapefile): one for nodes and one for edges.

The output files contain the following fields:

The **nodes** file contains

- `id`: the unique identifier of the node. The id goes from 0 to the number of exported nodes - 1, so it can be used as an index.
- `db_id`: the unique identifier of the node in the database.
- `x`: the x-coordinate of the node.
- `y`: the y-coordinate of the node.

The **edges** file contains:

- `u`: the `id` of the starting node of the edge.
- `v`: the `id` of the ending node of the edge.
- `db_id_from`: the unique identifier of the starting node in the database.
- `db_id_to`: the unique identifier of the ending node in the database.
- `length`: the length of the edge in meters.
- `speed`: the speed on the edge in km/h.


# Development Guide

## PostgreSQL Tests
For testing the PostgreSQL, we use the [pgTAP](https://pgtap.org/) framework. You can find more information about the framework in the [pgTAP manual](https://f-i-d-o.github.io/Manuals/Programming/Database/PostgreSQL%20Manual).


### Custom test executer
Because pgTAP provides only a basic function for executing tests, that for example, executes every single fixture even if a test filter is used, we created a custom test executer `mob_group_runtests` that can be used to run tests. The source code for this execution machinery can be found in the `SQL/tests/test_extensions.sql` file. The main difference compared to the default test runner:

- filter is applied to the test fixtures as well, not only to the tests
- tests are executed in a separate schema (`test_env` by default)


### Creating new tests
To create a new test, just create a test function in the appropriate test file in the `tests` directory. Tests have to be named `test_<function_name>_<test_description>`.

You can also create [*fixtures*](https://f-i-d-o.github.io/Manuals/Programming/Database/PostgreSQL%20Manual/#fixtures). To be compatible with the custom test executer you have to follow the naming convention `<fixture_type>_<function_name>_<test_description>`. Note that unlike other programming languages, here all fixtures of a certain type are executed at once, not just the onec with the name that matches the test name.

If you need to crete a test for a function or procedure that is not covered by the existing test files, create a new test file in the `tests` directory. The test file should be named `test_<function_name>.sql`.
