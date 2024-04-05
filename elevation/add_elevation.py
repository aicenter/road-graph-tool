import requests
import psycopg2
import json

url = 'http://localhost:8080/elevation/api'

# load configuration of db


def load_config():
    with open('config.json') as f:
        config = json.load(f)
    return config['database']

# load node ids and coords from db to dict


def load_coords():
    db_params = load_config()
    elevations = dict()
    query = """ SELECT node_id, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM nodes; """
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                for row in cur.fetchall():
                    node_id, lat, lon = row
                    coords = {"lat": lat, "lon": lon}
                    elevations[node_id] = coords
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)
    return elevations

# prepare json with coords for api request


def prepare_coords(elevation_dict):
    json_coord_dict = {
        'locations': []
    }
    for key in elevation_dict:
        json_coord_dict['locations'].append(elevation_dict[key])
    return json_coord_dict


# send request to api and get elevation data
def get_elevation(json_data):
    response = requests.post(url, json=json_data)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error:", response.status_code)
    return response.json()


# update elevations: add elevation to dict containing info about nodes
def update_elevations(coords_dict, json_elevation_dict):
    print("Start update elevations...")
    locations = json_elevation_dict.get('locations', [])
    total_locations = len(locations)
    for i, location in enumerate(locations, 1):
        lat = location.get('lat')
        lon = location.get('lon')
        ele = location.get('ele')
        for _, coords in coords_dict.items():
            if coords['lat'] == lat and coords['lon'] == lon:
                coords['ele'] = ele
                # Calculate progress percentage
                progress = i / total_locations * 100
                # Update loading bar
                print(
                    f"\rUpdating elevations: [{'#' * int(progress / 10):<10}] {progress:.2f}%", end='', flush=True)
                break
    return coords_dict


coords = load_coords()
json_coords = prepare_coords(coords)
json_elevations = get_elevation(json_coords)


# save data to a JSON file
def save_data_to_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f)


save_data_to_json(coords, 'coordinates.json')
save_data_to_json(json_elevations, 'elevations.json')

# print(len(json_elevations['locations']))
# elevations = update_elevations(coords, json_elevations)
# print(elevations)
# coords = {324309497: {"lat": 53.8371561, "lon": 23.8803151},
#           324307952: {"lat": 53.8455361, "lon": 23.8900327}}
# json_coords = {
#     "locations": [{"lat": 53.8371561, "lon": 23.8803151}, {"lat": 53.8455361, "lon": 23.8900327}]
# }
# json_elevations = {'locations': [{'lat': 53.8371561, 'lon': 23.8803151, 'ele': 94}, {
#     'lat': 53.8455361, 'lon': 23.8900327, 'ele': 113}]}
# elevations = update_elevations(coords, json_elevations)
# print(elevations)

# json_data = {
#     "locations": [{"lat": 53.8371561, "lon": 23.8803151}, {"lat": 53.8455361, "lon": 23.8900327}]
# }

# elevation_map = {(location['lat'], location['lon']): location['ele'] for location in elevation_data['locations']}


# load elevation from elevations dict to db
