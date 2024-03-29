# Graph Contraction 

This script focuses on contracting a graph based on road segments within a specified area. The program is designed to work with a remote database through an SSH tunnel, ensuring secure access to the database server.

## Features

- **Road Segments Table Creation**: Generates a temporary table containing road segments within a target area.
- **Graph Contraction**: Contracts the graph by creating a temporary table that holds the contraction information for each node.
- **Node Updates**: Updates the nodes in the database to mark them as contracted.
- **Edge Creation**: Generates edges for both contracted and non-contracted road segments.
- **Contraction Segments Generation**: Creates contraction segments to facilitate the creation of edges for contracted road segments.

## Configuration

Before running the script, ensure you have the following configurations set in `config.ini`:

- **SSH Configuration**: Set your SSH `private_key_path` and `server_username`. Optionally, you can set a `private_key_passphrase` if your private key is passphrase-protected.
- **Database Configuration**: Set your database `username` and `db_password`.

## Dependencies

- **psycopg2**: PostgreSQL database adapter for Python.
- **sshtunnel**: Creates an SSH tunnel for secure database connection.
- **PostgreSQL & PostGIS**: Ensure your database is set up with PostGIS extension for spatial queries.

## Usage

1. Ensure all configurations in `config.ini` are set correctly.
2. Run `main.py` to start the graph contraction process. The script will connect to the database through an SSH tunnel, create necessary tables and indexes, contract the graph, and generate edges for the contracted graph.

## Note

This project is designed to work with specific database schemas and requires access to a remote PostgreSQL database with PostGIS extension. Ensure your database schema matches the expectations of the script (e.g., `nodes`, `edges`, `road_segments` tables).


![procedure_contract_graph_in_area](https://github.com/aicenter/road-graph-tool/assets/25695606/8de0fd29-6500-4a13-a3c1-31b57f864c65)
