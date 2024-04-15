# Adding elevation to all nodes

* Author: Dominika Sidlova

## Description
This directory contains Python script for adding elevation to nodes in PostgreSQL database using REST API (elevation-calculator)[https://github.com/aicenter/elevation-calculator].

## Prerequisities
- psycopg2: PostgreSQL database adapter for Python.
- PostGIS: Ensure your database is set up with PostGIS extension for spatial queries.

## Usage

1. Run RestApiApplication in elevation-calculator
2. Run script add_elevation.py:
  - preprocess nodes (get coordinations from node geometry):
```sql
SELECT ST_Y(geom) AS latitude, ST_X(geom) AS longitude from nodes;
```
  - get elevation:  post (multiple) http://localhost:8080/elevation/api -> returns JSON

## Stats
Speed of processing and importing data into databases was tested on map of Germany.
Local processing: <insert-time>
Remote processing: <insert-time>

