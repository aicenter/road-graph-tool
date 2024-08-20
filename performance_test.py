import sys
import os
import time
import psutil
import subprocess
import psycopg2
from memory_profiler import profile
import platform

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS

def get_db_table_size(config: dict[str,str]):
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
                print("\nDB Table Sizes:")
                for row in rows:
                    print(f"Table: {row[0]}, Size: {row[1]}")
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

@profile
def import_and_monitor():
    """Function to monitor time, HDD usage, and run the import_osm_to_db function."""
    start_time = time.time()
    disk_usage_before = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Run the import function
    print("\n=== Running import_osm_to_db() ===")
    import_osm_to_db()

    # Calculate time and resource usage
    elapsed_time = time.time() - start_time
    disk_usage_after = psutil.disk_usage('/').used / (1024 ** 3)  # GB

    # Print time and resource usage
    print("\n=== Performance Metrics ===")
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"HDD used: {disk_usage_after - disk_usage_before:.2f} GB")

def monitor_performance(config: dict[str,str]):
    """Monitors and prints time, memory, HDD usage, and DB table sizes."""
    # Print hardware info
    get_hw_config()

    # Print DB table sizes before import
    print("\n=== Table size before import ===")
    get_db_table_size(config)

    # Run the import function
    import_and_monitor()

    # Print DB table sizes after import
    print("\n=== Table size after import ===")
    get_db_table_size(config)

def convert_b_to_GB(size):
    return round(size / (10**(9)), 2)

def get_hw_config():
    print("=== Hardware configuration ===")
    system_info = platform.uname()
    logical_cpu_count = psutil.cpu_count(logical=True)
    memory_info = psutil.virtual_memory()
    print(f"""
System: {system_info.system}
Release: {system_info.release}
Processor: {system_info.processor}
Logical cores: {logical_cpu_count}
Total memory: {convert_b_to_GB(memory_info.total)} GB
Used memory: {convert_b_to_GB(memory_info.used)} GB
Memory utilization: {memory_info.percent}%""")

def main():
    config = {
        "host": CREDENTIALS.host,
        "dbname": CREDENTIALS.db_name,
        "user": CREDENTIALS.username,
        "password": CREDENTIALS.db_password,
        "port": CREDENTIALS.db_server_port
    }
    if len(sys.argv) > 1 and sys.argv[1] in ["--import", "-i"]:
        monitor_performance(config)

if __name__ == '__main__':
    main()
