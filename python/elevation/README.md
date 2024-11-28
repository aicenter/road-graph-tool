# Adding elevation to all nodes

## Description
This directory contains Python script for adding elevation to nodes in PostgreSQL database using REST API provided by [elevation-calculator](https://github.com/aicenter/elevation-calculator).

## Prerequisites
- psycopg2: PostgreSQL database adapter for Python.
- PostGIS: Ensure your database is configured with PostGIS extension to enable spatial queries.
- elevation-calculator: Tool for calculating of elevation for given GPS coordinates.
- SRTM data: `elevation-calculator` requires SRTM data to be downloaded in advance (I recommend storing them in Google drive)
- Database Configuration: Ensure your database connection details are correctly set up in the `config.ini` file.

## Usage
1. Run REST API
    - The current version of REST API does NOT run on a remote server, so it must be executed locally. Run `RestApiApplication` class of  `elevation-calculator` application
    > **_NOTE:_** specify path to SRTM data in `elevation-calculator`
2. Run the [add_elevation.py](add_elevation.py) - provide the `schema` and `table_name` where the nodes are stored. The script will:
    - execute a query to retrieve coordinates from the specified `table_name` in database
    - preprocess the data to a format that can be submitted to REST API application - it's presumed that REST API returns the data in the same order it receives it
    - process the returned elevations and insert them in `elevations` (temporary table)
    - not working as it's too slow atm: update `table_name` with elevations from `elevations`
    
Example usage:
```bash
python add_elevation.py elevation -sch public
```

## Hints

* If running REST API locally results in an `java.lang.OutOfMemoryError: Java heap space` exception, 
increase heap space to 4GB 
    * **IntelliJ IDEA**: *Edit configurations* -> *Modify options*: *Add VM options* -> add `-Xmx4G` flag

## Performance
Speed of processing and importing data into databases was tested on map of Czech Republic and Germany. Nodes were split into even chunks of 5000 for faster processing.

<!-- More information about various speed-testings cases can be found in the `testing-manual.md` file. -->
### Testing specifications
The scripts were tested on two machines:
|  | **OS** | **CPU** | **RAM** |
|---|---|---|---|
| Macbook Pro 2020 | Sequioa 15.1.1 | Apple M1 | 16 GB |
| Lenovo Yoga | Ubuntu |  | 16 GB |

### Stats

#### Czech Republic - all nodes (78,906,836):

| Local database | **Time (s) on macOS** | **Time (s) on Ubuntu** |
|---|---|---|
| Query to load coordinations from DB | 199 |  |
| Get elevations from REST API elevation calculator | 520 |  |
| Process data | 62 |  |
| Query to store elevations to DB | 237 |  |
| **Total time** | **937** |  |

| Remote database | **Time (s) on macOS** | **Time (s) on Ubuntu** |
|---|---|---|
| Query to load coordinations from DB | 908 |  |
| Get elevations from REST API elevation calculator | 533 |  |
| Process data | 62 |  |
| Query to store elevations to DB | 2281 |  |
| **Total time** | **3787** |  |

#### Germany - highway nodes (81,444,269):

| Local database | **Time (s) on macOS** | **Time (s) on Ubuntu** |
|---|---|---|
| Query to load coordinations from DB |  |  |
| Get elevations from REST API elevation calculator | 520 |  |
| Process data |  |  |
| Query to store elevations to DB |  |  |
| **Total time** | **** |  |

| Remote database | **Time (s) on macOS** | **Time (s) on Ubuntu** |
|---|---|---|
| Query to load coordinations from DB | 481 |  |
| Get elevations from REST API elevation calculator | 520 |  |
| Process data | 139 |  |
| Query to store elevations to DB | 58 |  |
| **Total time** | **** |  |
