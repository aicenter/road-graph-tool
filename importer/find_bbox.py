import xml.etree.ElementTree as ET
import sys


def find_min_max(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    min_lon = float('inf')
    min_lat = float('inf')
    max_lon = float('-inf')
    max_lat = float('-inf')

    for node in root.findall('.//node'):
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        min_lon = min(min_lon, lon)
        min_lat = min(min_lat, lat)
        max_lon = max(max_lon, lon)
        max_lat = max(max_lat, lat)

    return min_lon, min_lat, max_lon, max_lat


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <json_file>")
        sys.exit(1)
    xml_file = sys.argv[1]
    min_lon, min_lat, max_lon, max_lat = find_min_max(xml_file)
    print(f"Boudning box:    {min_lon},{min_lat},{max_lon},{max_lat}")
