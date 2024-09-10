import argparse
from datetime import datetime
import os
import time
import psutil
import psycopg2
import platform
import json

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS

MARKDOWN_FILE = "resources/performance_report.md"
JSON_FILE = "resources/performance_report.json"

def file_exists(file: str) -> bool:
    """Checks if a file exists."""
    return os.path.isfile(file)

def format_time(seconds: float) -> str:
    """Return time in more readable format (minutes, hours)."""
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}min"
    elif minutes > 0:
        return f"{int(minutes)}min"
    else:
        return f"{int(sec)}s"

def generate_markdown_row(location: str, data: dict) -> str:
    """Return a generated markdown table row for a specific location."""
    performance_metrics = data.get("performance_metrics", {})
    file_size = data.get("file_size", "N/A")
    date = data.get("date_import", "N/A")
    db_table_sizes = data.get("db_table_sizes", {})

    time = format_time(performance_metrics.get("total_time", 0))
    nodes_size = db_table_sizes.get("nodes", "N/A")
    ways_size = db_table_sizes.get("ways", "N/A")
    relations_size = db_table_sizes.get("relations", "N/A")

    return f"| {location.title()} | {file_size} | {date} | {time} | {nodes_size} | {ways_size} | {relations_size} |"

def generate_markdown_table(data: dict) -> str:
    """Return a complete generated markdown table for all locations."""
    headers = ["Location", "File size", "Date of import", "Speed of import", "Nodes size", "Ways size", "Relations size"]
    
    table = ["| " + " | ".join(headers) + " |"]
    table.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for location, data in data.items():
        if location != "db_info":
            table.append(generate_markdown_row(location, data))
    
    return "\n".join(table)

def write_markdown(json_data: dict):
    """Write text to a MARKDOWN file."""
    system_info = json_data.get('system_info', {})
    cpu_info = json_data.get('cpu_info', {})
    memory_info = json_data.get('memory_info', {})
    disk_info = json_data.get('disk_info', {})

    markdown = []
    markdown.append(f"""# Performance
## Hardware configuration
- **System**: {system_info.get('system', 'N/A')}
- **Version**: {system_info.get('version', 'N/A')}
- **Logical cores**: {cpu_info.get('logical_cores', 'N/A')}
- **Total memory**: {memory_info.get('total_memory', 'N/A')} GB
- **Total disk space**: {disk_info.get('total_disk_space', 'N/A')} GB

### Database information with performance
""")
    
    data_info = json_data.get('data_info', {})
    for mode_conn, data in data_info.items():
        mode, conn = mode_conn.split('_')
        markdown.append(f"""**{mode.capitalize()} database - {conn} connection:**
- {data.get('db_info', 'N/A')}""")
        table = generate_markdown_table(data)
        markdown.append(table)

    text = '\n'.join(markdown)

    with open(MARKDOWN_FILE, mode='w') as f:
        f.write(text + "\n")

def write_json(metrics: dict):
    """Write data to JSON file."""
    with open(JSON_FILE, mode='w') as f:
        json.dump(metrics, f, indent=4)

def read_json() -> dict:
    """Return dictionary of the performance metrics from JSON file."""
    with open(JSON_FILE, 'r') as f:
        data = json.load(f)
    return data

def get_db_table_sizes(config: dict, schema: str) -> dict:
    """Return dictionary containing the sizes of all tables 
    in the **schema** of the database."""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT table_name, pg_size_pretty(size) 
                    FROM (
                        SELECT table_name, pg_total_relation_size(table_name::text) AS size
                        FROM information_schema.tables
                        WHERE table_schema = '{schema}'
                    ) AS subquery
                    WHERE size > 0;
                """)
                rows = cur.fetchall()
                table_sizes = {row[0]: row[1] for row in rows}
                return table_sizes
    except (psycopg2.DatabaseError, Exception) as error:
        raise error

def monitor_performance(config: dict, schema: str) -> dict:
    """Return dictionary of monitored time, file size, date of import and table sizes
    after running the **import_osm_to_db()** function."""
    start_time = time.time()

    # Run the import function
    file_size = import_osm_to_db(schema)

    elapsed_time = time.time() - start_time

    return {
            "performance_metrics": {"total_time": elapsed_time, "test_runs": 1},
            "file_size": convert_B_to_readable(file_size),
            "date_import": datetime.today().strftime('%d.%m.%Y'),
            "db_table_sizes": get_db_table_sizes(config, schema)
        }

def get_db_version(config: dict) -> str:
    """Return version of database."""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT split_part(version(), ' ', 1) || ' ' || current_setting('server_version') as db_info;")
                return cur.fetchone()[0]
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)

def monitor(config: dict, location: str, mode: str, network_conn: str, schema: str) -> dict:
    """Monitors HW metrics, time, memory and DB table sizes."""
    # Get hardware info
    hw_metrics = get_hw_config()

    mode_conn = f"{mode}_{network_conn}"
    hw_metrics["data_info"] = {
        mode_conn: {
            "db_info": get_db_version(config),
            location: monitor_performance(config, schema)
        }
    }
    return hw_metrics

def convert_B_to_readable(size) -> str:
    """Return a str of size in readable format rounded to two decimal places."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 10**3 or unit == 'GB':
            break
        size /= 10**3
    return f"{size:.2f} {unit}"


def get_hw_config() -> dict:
    """Return dictionary containing HW information about system, CPU count, memory and dick usage."""
    system_info = platform.uname()
    logical_cpu_count = psutil.cpu_count(logical=True)
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage('/')

    hw_metrics = {
    "system_info": {"system": system_info.system,
                    "version": system_info.version},
    "cpu_info": {"logical_cores": logical_cpu_count},
    "memory_info": {"total_memory":convert_B_to_readable(memory_info.total)},
    "disk_info": {"total_disk_space": convert_B_to_readable(disk_info.total)}}

    return hw_metrics

def get_network_config() -> str:
    """Return whether connection is wireless or ethernet."""
    net_info = psutil.net_if_stats()
    for key in net_info.keys():
        if key.startswith('wl'):
            connection = 'wireless'
        elif key.startswith('en'):
            connection = 'ethernet'
    return connection

def update_performance(current: dict, old: dict, location: str, mode: str, connection: str, config: dict):
    """Update JSON file with new data based on location, connection and mode."""
    mode_conn = f"{mode}_{connection}"
    location_data = old["data_info"].get(mode_conn, {}).get(location, {})
    if location_data:
        # compare and update location
        location_data["performance_metrics"]["test_runs"] += 1
        test_runs = location_data["performance_metrics"]["test_runs"]
        total_time = location_data["performance_metrics"]["total_time"] + current['performance_metrics']["total_time"]

        avg_time = total_time / test_runs

        location_data["performance_metrics"]["total_time"] = avg_time
    else:
        if mode_conn in old["data_info"]:
            # add location with metrics
            old["data_info"][mode_conn][location] = current
        else:
            # create mode_conn and add location with metrics
            version_info = get_db_version(config)
            old["data_info"][mode_conn] = {"db_info": version_info,
                                           location: current}

def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Performance monitoring and OSM import tool")

    subparsers = parser.add_subparsers(dest='command', required=True)
    
    loc_parser = subparsers.add_parser('l', help="Specify the name of location to include in statistics.")
    loc_parser.add_argument('location', help="Specify the location name.")
    loc_parser.add_argument('-m', dest='mode', required=True, help="Specify the database mode.")
    loc_parser.add_argument('-s', dest='schema', required=True, help="Specify the database schema.")
    
    subparsers.add_parser('md', help="Convert JSON to Markdown.")
    return parser.parse_args(arg_list)

def main(arg_list: list[str] | None = None):
    config = {
        "host": CREDENTIALS.host,
        "dbname": CREDENTIALS.db_name,
        "user": CREDENTIALS.username,
        "password": CREDENTIALS.db_password,
        "port": CREDENTIALS.db_server_port
    }
    args = parse_args(arg_list)
    match args.command:
        case 'md':
            json_data = read_json()
            write_markdown(json_data)
        case 'l':
            location = args.location
            mode = args.mode
            schema = args.schema
            conn = get_network_config()
            if file_exists(JSON_FILE):
                metrics = read_json()
                new_metrics = monitor_performance(config, schema)
                update_performance(new_metrics, metrics, location, mode, conn, config)
                write_json(metrics)
            else:
                metrics = monitor(config, location, mode, conn, schema)
                write_json(metrics)


if __name__ == '__main__':
    main()
    # main(['l', 'czechia', '-m', 'remote', '-s', 'osm_testing'])
    # main(['l', 'germany', '-m', 'remote', '-s', 'osm_testing'])