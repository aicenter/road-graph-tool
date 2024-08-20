import sys
import time
import psutil
import subprocess
import psycopg2
from memory_profiler import profile

from scripts.process_osm import import_osm_to_db
from roadgraphtool.credentials_config import CREDENTIALS as config

def run_command(command):
    """Helper function to run shell commands and capture their output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_db_table_size():
    """Prints the sizes of all tables in the public schema of the database."""
    # Establish a DB connection for printing table sizes
    conn = psycopg2.connect(
        dbname=config.db_name, 
        user=config.username, 
        password=config.db_password, 
        host=config.db_host,
        port=config.db_server_port
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT table_name, pg_size_pretty(pg_total_relation_size(table_name::text))
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    rows = cur.fetchall()
    print("\nDB Table Sizes:")
    for row in rows:
        print(f"Table: {row[0]}, Size: {row[1]}")
    
    # Close DB connection
    cur.close()
    conn.close()

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
    print(f"Total Execution Time: {elapsed_time:.2f} seconds")
    print(f"HDD Used: {disk_usage_after - disk_usage_before:.2f} GB")

def monitor_performance():
    """Monitors and prints time, memory, HDD usage, and DB table sizes."""
    # Print hardware and network info
    # print("=== Hardware and Network Configuration ===")
    # print("\nDisk Info:\n" + run_command("df -h"))

    # Print DB table sizes before import
    print("\n=== Table size before import ===")
    get_db_table_size()

    # Run the import function
    import_and_monitor()

    # Print DB table sizes after import
    print("\n=== Table size after import ===")
    get_db_table_size()

def parse_args():
    pass

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ["--import", "-i"]:
        monitor_performance()

if __name__ == '__main__':
    main()
