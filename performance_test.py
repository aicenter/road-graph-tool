import time
import psutil
import psycopg2
import platform

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS

markdown_file = "performance_report.md"

def write_to_markdown(text, mode='a'):
    """Helper function to write text to a markdown file."""
    with open(markdown_file, mode) as f:
        f.write(text + "\n")

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
                table_sizes = "\n".join([f"- **Table**: {row[0]}, **Size**: {row[1]}" for row in rows])
                return table_sizes
    except (psycopg2.DatabaseError, Exception) as error:
        return str(error)

# @profile
def import_and_monitor():
    """Function to monitor time, HDD usage, and run the import_osm_to_db function."""
    start_time = time.time()
    disk_usage_before = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Run the import function
    import_osm_to_db()

    # Calculate time and resource usage
    elapsed_time = time.time() - start_time
    disk_usage_after = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Log time and resource usage
    write_to_markdown("\n## Performance metrics")
    write_to_markdown(f"- **Total execution time**: {elapsed_time:.2f} seconds")
    write_to_markdown(f"- **HDD used**: {disk_usage_after - disk_usage_before:.2f} GB")

def monitor_performance(config: dict[str,str]):
    """Monitors and prints time, memory, HDD usage, and DB table sizes."""
    # Print hardware info
    get_hw_config()

    # Get DB table sizes before import
    sizes_before = get_db_table_size(config)
    # Run the import function
    import_and_monitor()
    # Get DB table sizes after import
    sizes_after = get_db_table_size(config)

    write_to_markdown("\n## Table sizes:")
    write_to_markdown("### Before import")
    write_to_markdown(sizes_before)
    write_to_markdown("### After import")
    write_to_markdown(sizes_after)

def convert_b_to_GB(size):
    return round(size / (10**(9)), 2)

def get_hw_config():
    write_to_markdown("## Hardware configuration", mode='w')
    system_info = platform.uname()
    logical_cpu_count = psutil.cpu_count(logical=True)
    memory_info = psutil.virtual_memory()
    hw_info = f"""
### System Information:
- **System**: {system_info.system}
- **Release**: {system_info.release}
- **Processor**: {system_info.processor}

### CPU Information:
- **Logical Cores**: {logical_cpu_count}

### Memory Information:
- **Total Memory**: {convert_b_to_GB(memory_info.total)} GB
- **Used Memory**: {convert_b_to_GB(memory_info.used)} GB
- **Memory Utilization**: {memory_info.percent}%"""
    write_to_markdown(hw_info)

def main():
    config = {
        "host": CREDENTIALS.host,
        "dbname": CREDENTIALS.db_name,
        "user": CREDENTIALS.username,
        "password": CREDENTIALS.db_password,
        "port": CREDENTIALS.db_server_port
    }
    monitor_performance(config)

if __name__ == '__main__':
    main()
