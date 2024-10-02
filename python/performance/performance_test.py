"""
This Python script is used for testing performance of importing or main pipeline.
Results are saved to 'python/performance/performance_report.json' JSON file. To generate markdown 
from aformentioned JSON file, run script with 'md' tag.

Run time is tracked as summation of each run along with run count - average run time is calculated 
when markdown is being generated.
"""
import argparse
from datetime import datetime
import os
import re
import subprocess
import time
import psutil
import psycopg2
import platform
import json

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS
from scripts.main import main as pipeline_main

MARKDOWN_FILE = "python/performance/perf_report.md"
JSON_FILE = "python/performance/performance_report.json"

def get_osm2pgsql_version() -> str:
    """Return version of osm2pgsql."""
    result = subprocess.run(['osm2pgsql', '--version'], capture_output=True, text=True)
    
    if result.returncode == 0:
        match = re.search(r'osm2pgsql version (\d+\.\d+\.\d+)', result.stderr)
        if match:
            return match.group(1)
    return "Error: Unable to fetch version."

def file_exists(file: str) -> bool:
    """Return True if a file exists."""
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
    
def get_table_size_from_dict(table: str, size_dict: dict) -> str:
    regex = re.compile(r"\w*" + re.escape(table) + r"\b")
    for t in size_dict.keys():
        if regex.match(t):
            return size_dict.get(t, "N/A")
    return "N/A" 

def generate_markdown_row(location: str, data: dict) -> str:
    """Return a generated markdown table row for a specific location."""
    performance_metrics = data.get("performance_metrics", {})
    file_size = data.get("file_size", "N/A")
    date = data.get("date_import", "N/A")
    db_table_sizes = data.get("db_table_sizes", {})

    total_time = performance_metrics.get("total_time", 0)
    runs = performance_metrics.get("test_runs", 1)

    time = format_time(total_time / runs)

    nodes_size = convert_to_readable_size(int(get_table_size_from_dict("nodes", db_table_sizes)))
    ways_size = convert_to_readable_size(int(get_table_size_from_dict("ways", db_table_sizes)))
    relations_size = convert_to_readable_size(int(get_table_size_from_dict("relations", db_table_sizes)))

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

def write_markdown(json_data: dict, header: str = ""):
    """Write text to a MARKDOWN file."""
    system_info = json_data.get('system_info', {})
    cpu_info = json_data.get('cpu_info', {})
    memory_info = json_data.get('memory_info', {})
    disk_info = json_data.get('disk_info', {})
    osm_info = json_data.get('osm_info',{})

    markdown = []
    markdown.append(f"""# Performance {header}
## Hardware configuration
- **System**: {system_info.get('system', 'N/A')}
- **Version**: {system_info.get('version', 'N/A')}
- **Logical cores**: {cpu_info.get('logical_cores', 'N/A')}
- **Total memory**: {memory_info.get('total_memory', 'N/A')} GB
- **Total disk space**: {disk_info.get('total_disk_space', 'N/A')} GB
- **osm2pgsql version**: {osm_info.get('osm_version', 'N/A')}

## Database information with performance""")
    
    data_info = json_data.get('data_info', {})
    for mode_conn, data in data_info.items():
        mode, conn = mode_conn.split('_')
        markdown.append(f"""\n**{mode.capitalize()} database - {conn} connection:**
- {data.get('db_info', 'N/A')}\n""")
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
                    SELECT table_name, size
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

def monitor_performance(config: dict, input_file: str, schema: str, style_file: str) -> dict:
    """Return dictionary of monitored time, file size, date of import and table sizes
    after running the **import_osm_to_db()** function."""
    start_time = time.time()

    if input_file:
        file_size = import_osm_to_db(input_file, style_file, schema=schema)
    else:
        # TODO:
        area_id = 51 # placeholder - area id based on data
        pipeline_main(['a', area_id, '-i', '-sf', style_file])

    elapsed_time = time.time() - start_time

    return {
            "performance_metrics": {"total_time": elapsed_time, "test_runs": 1},
            "file_size": convert_to_readable_size(file_size),
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

def monitor(config: dict, input_file: str, location: str, mode: str, network_conn: str, schema: str, style_file: str) -> dict:
    """Monitors HW metrics, time, memory and DB table sizes."""
    # Get hardware info
    hw_metrics = get_hw_config()

    mode_conn = f"{mode}_{network_conn}"
    hw_metrics["data_info"] = {
        mode_conn: {
            "db_info": get_db_version(config),
            location: monitor_performance(config, input_file, schema, style_file)
        }
    }
    return hw_metrics

def convert_to_readable_size(size: int) -> str:
    """Converts a size in bytes to a more readable format, rounding to two decimal places, and returns it as string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 10**3 or unit == 'GB':
            break
        size /= 10**3
    return f"{size:.2f} {unit}"

def extract_version(text: str) -> str:
    """Return short kernel version."""
    match = re.search(r'\d+\.\d+\.\d+-Ubuntu', text)
    if match:
        return match.group(0)
    return None

def get_hw_config() -> dict:
    """Return dictionary containing HW information about system, CPU count, memory and dick usage."""
    system_info = platform.uname()
    logical_cpu_count = psutil.cpu_count(logical=True)
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage('/')

    hw_metrics = {
    "system_info": {"system": system_info.system,
                    "version": extract_version(system_info.version)},
    "cpu_info": {"logical_cores": logical_cpu_count},
    "memory_info": {"total_memory": convert_to_readable_size(memory_info.total)},
    "disk_info": {"total_disk_space": convert_to_readable_size(disk_info.total)},
    "osm_info": {"osm_version": get_osm2pgsql_version()}}

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
        # update location metrics
        location_data["performance_metrics"]["test_runs"] += 1
        location_data["performance_metrics"]["total_time"] = location_data["performance_metrics"]["total_time"] + current['performance_metrics']["total_time"]
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
    parser = argparse.ArgumentParser(description="Performance monitoring of OSM import tool or whole pipeline")

    subparsers = parser.add_subparsers(dest='command', required=True)
    
    loc_parser = subparsers.add_parser('l', help="Specify the name of location to include in statistics.")
    loc_parser.add_argument('location', help="Specify the location name.")
    loc_parser.add_argument('-i', dest='input_file', help="Enable performance test of importing only.")
    loc_parser.add_argument('-m', dest='mode', required=True, help="Specify the database mode (local/remote) for '-i' flag.")
    loc_parser.add_argument('-s', dest='schema', required=True, help="Specify the database schema for '-i' flag.")
    loc_parser.add_argument("-sf", dest="style_file", default="resources/lua_styles/default.lua", help="Path to style file for '-i' flag.")
    
    md_parser = subparsers.add_parser('md', help="Convert JSON to Markdown.")
    md_parser.add_argument('-mh', dest='header', default="", help="Specify header for the Markdown output.")

    return parser.parse_args(arg_list)

def main(arg_list: list[str] | None = None):
    config = {
        "host": CREDENTIALS.db_host,
        "dbname": CREDENTIALS.db_name,
        "user": CREDENTIALS.username,
        "password": CREDENTIALS.db_password,
        "port": CREDENTIALS.db_server_port
    }
    args = parse_args(arg_list)
    match args.command:
        case 'md':
            json_data = read_json()
            header = f"of {args.header}" if args.header else args.header
            write_markdown(json_data, header)
        case 'l':
            location = args.location
            mode = args.mode
            schema = args.schema
            conn = get_network_config()
            if file_exists(JSON_FILE):
                metrics = read_json()
                new_metrics = monitor_performance(config, args.input_file, schema, args.style_file)
                update_performance(new_metrics, metrics, location, mode, conn, config)
                write_json(metrics)
            else:
                metrics = monitor(config, args.input_file, location, mode, conn, schema, args.style_file)
                write_json(metrics)


if __name__ == '__main__':
    # main()
    main(['md', '-mh', 'importing from local machine'])
    # main(['l', 'monaco', '-i', '-m','local', '-s', 'osm_testing', '-sf', 'resources/lua_styles/pipeline.lua'])
    # main(['l', 'monaco', '-m','local', '-s', 'osm_testing', '-i', '-sf', 'resources/lua_styles/pipeline.lua'])
    # main(['l','czechia', '-i','to_import.osm.pbf', '-m','local', '-s', 'osm_testing'])
    # main(['l', 'czechia','-h'])