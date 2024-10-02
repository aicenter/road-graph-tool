# Adding elevation to all nodes

## Description
This directory contains Python script for adding elevation to nodes in PostgreSQL database using REST API provided by [elevation-calculator](https://github.com/aicenter/elevation-calculator).

## Prerequisites
- psycopg2: PostgreSQL database adapter for Python.
- PostGIS: Ensure your database is configured with PostGIS extension to enable spatial queries.
- SRTM data: `elevation-calculator` requires SRTM data to be downloaded in advance.
- Database Configuration: Ensure your database connection details are correctly set up in the `config.ini` file.

## Usage
1. Run REST API
    - The current version of REST API does NOT run on a remote server, so it must be executed locally. Run `RestApiApplication` class of  `elevation-calculator` application
2. Run the [add_elevation.py](add_elevation.py) 
Provide the `table_name` where the nodes are stored as an argument. The script will:
    - execute a query to retrieve coordinates from the specified `table_name` in database
    - preprocess the data to a format that can be submitted to REST API application - it's presumed that REST API returns the data in the same order it receives it
    - process the returned elevations and update the `table_name` with the new data
    
Example usage:
```
python3 add_elevation.py elevation
```


## Stats
Speed of processing and importing data into databases was tested on map of Germany.

<!-- More information about various speed-testings cases can be found in the `testing-manual.md` file. -->
