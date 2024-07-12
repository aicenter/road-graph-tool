# Adding elevation to all nodes

* Author: Dominika Sidlova

## Description
This directory contains Python script for adding elevation to nodes in PostgreSQL database using REST API (elevation-calculator)[https://github.com/aicenter/elevation-calculator].

## Prerequisities
- psycopg2: PostgreSQL database adapter for Python.
- PostGIS: Ensure your database is set up with PostGIS extension for spatial queries.

## Usage

1. Local REST API run: Run RestApiApplication in elevation-calculator
2. Specify parameters for your database configuration in `config.ini` file
3. Run script add_elevation.py with `table_name` (table where the nodes are stored) parameter. The script:
    - uses query to get coordinates from `table_name` in database
    - preprocesses the data to a format that can be posted to REST API application - it's presumed that REST API returns the data in the same order it receives it
    - processes the returned coordinates with elevations and stores them in `table_name` in database
    - e.g. 
    ```bash
    python3 add_elevation.py elevation
    ```

## Stats
Speed of processing and importing data into databases was tested on map of Germany.

More information about various speed-testings cases can be found in the `testing-manual.md` file.
