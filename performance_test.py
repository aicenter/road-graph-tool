import argparse
import time
import psutil
import psycopg2
import platform
import json

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS

markdown_file = "performance_report.md"
json_file = "performance_report.json"

def write_markdown(json_data: dict):
    """Helper function to write text to a markdown file."""
    markdown = []

    markdown.append('## Hardware Configuration')

    system_info = json_data.get('system_info', {})
    markdown.append(f"""
### System Information
- **System**: {system_info.get('system', 'N/A')}
- **Release**: {system_info.get('release', 'N/A')}
- **Processor**: {system_info.get('processor', 'N/A')}""")
    
    cpu_info = json_data.get('cpu_info', {})
    markdown.append(f"""
### CPU Information
- **Logical Cores**: {cpu_info.get('logical_cores', 'N/A')}""")

    memory_info = json_data.get('memory_info', {})
    markdown.append(f"""
### Memory Information
- **Total Memory**: {memory_info.get('total_memory', 'N/A')} GB
- **Used Memory**: {memory_info.get('used_memory', 'N/A')} GB
- **Memory Utilization**: {memory_info.get('memory_utilization', 'N/A')}%""")

    performance_metrics = json_data.get('performance_metrics', {})
    markdown.append(f"""
## Performance Metrics
- **Total Time**: {performance_metrics.get('total_time', 'N/A')} s
- **HDD Used**: {performance_metrics.get('hdd_used', 'N/A')} GB
- **Test Runs**: {performance_metrics.get('test_runs', 'N/A')}
""")

    db_table_sizes = json_data.get('db_table_sizes', {})

    before_import = db_table_sizes.get('before_import', {})
    before_import_lines = '\n'.join(f"- **{key.replace('_', ' ').title()}**: {value}" for key, value in before_import.items())
    markdown.append(f"""## Table Sizes
### Before Import
{before_import_lines}\n""")

    after_import = db_table_sizes.get('after_import', {})
    after_import_lines = '\n'.join(f"- **{key.replace('_', ' ').title()}**: {value}" for key, value in after_import.items())
    markdown.append(f"""### After Import
{after_import_lines}""")

    text = '\n'.join(markdown)

    with open(markdown_file, mode='w') as f:
        f.write(text + "\n")

def write_json(data, mode='w'):
    """Helper function to write data to a JSON file."""
    with open(json_file, mode) as f:
        json.dump(data, f, indent=4)

def read_json() -> dict:
    """Reads the performance metrics from the JSON file and returns them as a dictionary."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data

def get_db_table_size(config: dict[str,str]) -> str:
    """Prints the sizes of all tables in the public schema of the database."""
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
        return str(error)

def import_and_monitor() -> dict:
    """Function to monitor time, HDD usage, and run the import_osm_to_db function."""
    start_time = time.time()
    disk_usage_before = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Run the import function
    import_osm_to_db()

    # Calculate time and resource usage
    elapsed_time = time.time() - start_time
    disk_usage_after = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Log time and resource usage
    performance_metrics = {"performance_metrics":
        {"total_time": elapsed_time,
        "hdd_used": disk_usage_after - disk_usage_before,
        "test_runs": 1}
    }
    return performance_metrics

def compare_metrics(current_metrics: dict, old_metrics: dict) -> dict:
    """Compare current metrics with old metrics and update the averages."""
    updated_metrics = old_metrics
    updated_metrics["performance_metrics"]["Tests run"] += 1

    updated_metrics["performance_metrics"]["Total execution time"].append(current_metrics["Total execution time"])
    avg_time = sum(updated_metrics["performance_metrics"]["Total execution time"]) / updated_metrics["performance_metrics"]["Tests run"]

    updated_metrics["performance_metrics"]["HDD used"].append(current_metrics["HDD used"])
    avg_hdd = sum(updated_metrics["performance_metrics"]["HDD used"]) / updated_metrics["performance_metrics"]["Tests run"]

    # Update metrics with averages
    updated_metrics["performance_metrics"]["Average execution time"] = avg_time
    updated_metrics["performance_metrics"]["Average HDD used"] = avg_hdd

    return updated_metrics

def monitor_performance(config: dict[str,str]):
    """Monitors time, memory, HDD usage, and DB table sizes."""
    # Get hardware info
    hw_metrics = get_hw_config()

    # Get DB table sizes before import
    sizes_before = get_db_table_size(config)

    # Run the import function
    performance_metrics = import_and_monitor()

    # Get DB table sizes after import
    sizes_after = get_db_table_size(config)

    table_metrics = {"db_table_sizes": {"before_import": sizes_before, "after_import": sizes_after}}

    hw_metrics.update(performance_metrics)
    hw_metrics.update(table_metrics)
    return hw_metrics

def convert_b_to_GB(size):
    return round(size / (10**(9)), 2)

def get_hw_config() -> dict:
    system_info = platform.uname()
    logical_cpu_count = psutil.cpu_count(logical=True)
    memory_info = psutil.virtual_memory()
    hw_metrics = {
    "system_info": {"system": system_info.system,
                    "release": system_info.release,
                    "processor": system_info.processor},
    "cpu_info": {"logical_cores": logical_cpu_count},
    "memory_info": {"total_memory":convert_b_to_GB(memory_info.total),
                    "used_memory": convert_b_to_GB(memory_info.used),
                    "memory_utilization": memory_info.percent}
    }
    return hw_metrics

def compare(current: dict, old: dict) -> dict:
    updated = old["performance_metrics"]

    updated["test_runs"] += 1
    test_count = updated["test_runs"]
    total_time = updated["total_time"] + current["total_time"]
    hdd_used = updated["hdd_used"] + current["hdd_used"]

    avg_time = total_time / test_count
    avg_hdd = hdd_used / test_count

    updated["total_time"] = avg_time
    updated["hdd_used"] = avg_hdd

    return old

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Performance monitoring and OSM import tool")
    parser.add_argument('-c', '--compare', dest='compare', action='store_true', help="Run import and compare performance metrics with previous runs")
    parser.add_argument('-md', '--markdown', dest='md', action='store_true', help="Convert JSON to Markdown")
    return parser.parse_args()

def main():
    config = {
        "host": CREDENTIALS.host,
        "dbname": CREDENTIALS.db_name,
        "user": CREDENTIALS.username,
        "password": CREDENTIALS.db_password,
        "port": CREDENTIALS.db_server_port
    }
    args = parse_args()
    if args.compare:
        performance_metrics = import_and_monitor()["performance_metrics"]
        old_metrics = read_json()
        metrics = compare(performance_metrics, old_metrics)
    else:
        metrics = monitor_performance(config)
    write_json(metrics)
    if args.md:
        json_dict = read_json()
        write_markdown(json_dict)

if __name__ == '__main__':
    main()
