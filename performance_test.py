import argparse
import os
import time
import psutil
import psycopg2
import platform
import json

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS

markdown_file = "performance_report.md"
json_file = "performance_report.json"

def json_exists() -> bool:
    return os.path.isfile(json_file)

def location_exists(location: str, json_data: dict) -> bool:
    return location in json_data['locations'].keys()

def format_time(seconds: float) -> str:
    """Converts time in seconds to a more readable format (minutes, hours)."""
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}mins"
    elif minutes > 0:
        return f"{int(minutes)}mins"
    else:
        return f"{int(sec)}s"

def generate_markdown_row(location: str, data: dict) -> str:
    """Generates a markdown table row for a specific location."""
    performance_metrics = data.get("performance_metrics", {})
    db_table_sizes = data.get("db_table_sizes", {})

    time = format_time(performance_metrics.get("total_time", 0))
    # hdd_used = f"{round(performance_metrics.get('hdd_used', 0), 2)} GB"
    
    nodes_size = db_table_sizes.get("nodes", "N/A")
    ways_size = db_table_sizes.get("ways", "N/A")
    relations_size = db_table_sizes.get("relations", "N/A")

    return f"| {location} | {time} | {nodes_size} | {ways_size} | {relations_size} |"
    # return f"| {location} | {time} | {hdd_used} | {nodes_size} | {ways_size} | {relations_size} |"

def generate_markdown_table(json_data: dict) -> str:
    """Generates a complete markdown table for all locations."""
    headers = ["Location", "Speed", "Nodes size", "Ways size", "Relations size"]
    # headers = ["Location", "Speed", "HDD used", "Nodes size", "Ways size", "Relations size"]
    
    # Create table header
    table = ["| " + " | ".join(headers) + " |"]
    table.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    # Add rows for each location
    for location, data in json_data.get('locations', {}).items():
        table.append(generate_markdown_row(location, data))
    
    return "\n".join(table)

def write_markdown(json_data: dict):
    """Helper function to write text to a markdown file."""
    system_info = json_data.get('system_info', {})
    cpu_info = json_data.get('cpu_info', {})
    memory_info = json_data.get('memory_info', {})
    disk_info = json_data.get('disk_info', {})
    network_info = json_data.get('network_info', {})
    database_info = json_data.get('db_info', 'N/A')
    markdown = []
    markdown.append(f"""# Performance
## Hardware configuration
### System information
- **System**: {system_info.get('system', 'N/A')}
- **Release**: {system_info.get('release', 'N/A')}
- **Processor**: {system_info.get('processor', 'N/A')}

### Network information:
- **Connection**: {network_info.get('connection', 'N/A')}

### CPU information
- **Logical cores**: {cpu_info.get('logical_cores', 'N/A')}

### Memory information
- **Total memory**: {memory_info.get('total_memory', 'N/A')} GB

### Disk information
- **Total disk space**: {disk_info.get('total_disk_space', 'N/A')} GB
- **Free disk space**: {disk_info.get('free_disk_space', 'N/A')} GB

### Database information
- **Total disk space**: {database_info}
""")
    
    markdown.append("## Performance metrics and table sizes")
    markdown.append(generate_markdown_table(json_data))

    text = '\n'.join(markdown)

    with open(markdown_file, mode='w') as f:
        f.write(text + "\n")

def write_json(metrics: dict):
    """Writes data to a JSON file."""
    with open(json_file, mode='w') as f:
        json.dump(metrics, f, indent=4)

def read_json() -> dict:
    """Reads the performance metrics from the JSON file and 
    returns them as a dictionary."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data

def get_db_table_size(config: dict) -> dict:
    """Returns a dictionary contains the sizes of all tables 
    in the public schema of the database."""
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name, pg_size_pretty(pg_total_relation_size(table_name::text))
                    FROM information_schema.tables
                    WHERE table_schema = 'public';
                """)
                rows = cur.fetchall()
                table_sizes = {row[0]: row[1] for row in rows}
                return table_sizes
    except (psycopg2.DatabaseError, Exception) as error:
        raise error

def monitor_performance(config: dict, store_table_sizes: bool) -> dict:
    """Function to monitor time, HDD usage, and run the import_osm_to_db function."""
    start_time = time.time()
    # disk_usage_before = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Run the import function
    import_osm_to_db()

    # Calculate time and resource usage
    elapsed_time = time.time() - start_time
    # disk_usage_after = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Log time and resource usage
    performance_metrics = {"performance_metrics":
        {"total_time": elapsed_time,
        # "hdd_used": disk_usage_after - disk_usage_before,
        "test_runs": 1}}
    
    # Get DB table sizes
    if store_table_sizes:
        table_sizes = get_db_table_size(config)
        table_metrics = {"db_table_sizes": table_sizes}

        performance_metrics.update(table_metrics)
    
    return performance_metrics

def monitor(config: dict, location:str, store_table_sizes: bool) -> dict:
    """Monitors time, memory, HDD usage, and DB table sizes."""
    # Get hardware info
    hw_metrics = get_hw_config(config)
    hw_metrics.update({"locations": {}})

    # Get performance info
    performance_metrics = monitor_performance(config, store_table_sizes)

    hw_metrics['locations'][location] = performance_metrics

    return hw_metrics

def convert_b_to_GB(size):
    return round(size / (10**(9)), 2)

def get_hw_config(config: dict) -> dict:
    system_info = platform.uname()
    logical_cpu_count = psutil.cpu_count(logical=True)
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage('/')
    network_conn = get_network_config()

    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW server_version;")
                version_info = cur.fetchone()[0]
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)

    hw_metrics = {
    "system_info": {"system": system_info.system,
                    "release": system_info.release,
                    "processor": system_info.processor},
    "cpu_info": {"logical_cores": logical_cpu_count},
    "network_info": {"connection": network_conn},
    "memory_info": {"total_memory":convert_b_to_GB(memory_info.total)},
    "disk_info": {"total_disk_space": convert_b_to_GB(disk_info.total),
                  "free_disk_space": convert_b_to_GB(disk_info.free)},
    "db_info": version_info}

    return hw_metrics

def get_network_config() -> str:
    net_info = psutil.net_if_stats()
    for key in net_info.keys():
        if key.startswith('wl'):
            connection = 'wireless'
        elif key.startswith('en'):
            connection = 'ethernet'
    return connection

def compare_and_update(current: dict, old: dict, location: str):
    locations = old["locations"]
    if location not in locations.keys():
        locations[location] = current
    else:
        updated = locations[location]['performance_metrics']

        updated["test_runs"] += 1
        test_count = updated["test_runs"]
        total_time = updated["total_time"] + current['performance_metrics']["total_time"]
        hdd_used = updated["hdd_used"] + current['performance_metrics']["hdd_used"]

        avg_time = total_time / test_count
        avg_hdd = hdd_used / test_count

        updated["total_time"] = avg_time
        updated["hdd_used"] = avg_hdd

def parse_args(arg_list: list[str] | None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Performance monitoring and OSM import tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-loc', help="Specify the name of location to include in statistics.")
    group.add_argument('-md', dest='md', action='store_true', help="Convert JSON to Markdown.")
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

    if args.md:
        json_dict = read_json()
        write_markdown(json_dict)
    else:
        location = args.loc
        store_table_sizes = True
        if json_exists():
            metrics = read_json()
            if location_exists(location, metrics):
                store_table_sizes = False
            new_metrics = monitor_performance(config, store_table_sizes)
            compare_and_update(new_metrics, metrics, location)
            write_json(metrics)
        else:
            metrics = monitor(config, location, store_table_sizes)
            write_json(metrics)


if __name__ == '__main__':
    main()