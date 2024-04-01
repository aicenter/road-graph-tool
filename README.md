# Network Nodes Selector

This Python script is designed to connect to a PostgreSQL database through an SSH tunnel and execute a stored procedure to select network nodes within a specified area. It utilizes the `psycopg2` library for database connections and the `sshtunnel` library to securely connect to the database server over SSH.

## Features

- **SSH Tunneling**: Securely connects to the database server over SSH using the `sshtunnel` library.
- **Database Interaction**: Executes a stored procedure to select network nodes within a specified area using the `psycopg2` library.
- **Logging**: Provides logging for server connection, database connection, and the execution of the stored procedure.

## Configuration

Before running the script, ensure you have the following configurations set in `config.ini`:

- **SSH Configuration**: Set your SSH `private_key_path` and `server_username`. Optionally, you can set a `private_key_passphrase` if your private key is passphrase-protected.
- **Database Configuration**: Set your database `username`, `db_password`, `db_host` and `db_name`.

## Dependencies

- **psycopg2**: PostgreSQL database adapter for Python.
- **sshtunnel**: Creates an SSH tunnel for secure database connection.
- **PostgreSQL & PostGIS**: Ensure your database is set up with PostGIS extension for spatial queries.

## Usage

1. Ensure all configurations in `config.ini` are set correctly.
2. Run `main.py` to start the selecting process. The script will connect to the database through an SSH tunnel and print list of selected nodes.