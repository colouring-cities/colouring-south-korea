"""Join csv data to buildings

Example usage (replace URL with test/staging/localhost as necessary, API key with real key for
the appropriate site):

    python load_csv.py \
        https://colouring.london \
        a0a00000-0a00-0aaa-a0a0-0000aaaa0000 \
        data.csv

The optional last argument specifies which columns should be parsed as JSON values.
This is required for example for columns of array type to be processed by the API correctly.
Otherwise, those values would be treated as a string and not an array.

An example usage with the json_columns argument (other values in the example are placeholders):
    python load_csv.py \
        https://colouring.london \
        a0a00000-0a00-0aaa-a0a0-0000aaaa0000 \
        data.csv \
        current_landuse_group,date_url

This script uses the HTTP API, and can process CSV files which identify buildings by id, TOID,
UPRN.

The process:
    - assume first line of the CSV is a header, where column names are either
        - building identifiers - one of:
            - building_id
            - toid
            - uprn
        - building data field names
    - read through lines of CSV:
        - use building id if provided
            - else lookup by toid
            - else lookup by uprn
            - else locate building by representative point
        - (optional) parse JSON column values
        - update building

TODO extend to allow latitude,longitude or easting,northing columns and lookup by location.

"""
import csv
import json
import os
import sys

import requests
from retrying import retry


def main(base_url, api_key, source_file, json_columns):
    """Read from file, update buildings
    """
    with open(source_file, 'r') as source:
        reader = csv.DictReader(source)
        for line in reader:
            building_id = find_building(line, base_url)
            line = parse_json_columns(line, json_columns)

            if building_id is None:
                continue

            if 'sust_dec' in line and line['sust_dec'] == '':
                del line['sust_dec']

            response_code, response_data = update_building(building_id, line, api_key, base_url)
            if response_code != 200:
                print('ERROR', building_id, response_code, response_data)
            else:
                print('DEBUG', building_id, response_code, response_data)


@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
def update_building(building_id, data, api_key, base_url):
    """Save data to a building
    """
    r = requests.post(
        "{}/api/buildings/{}.json".format(base_url, building_id),
        params={'api_key': api_key},
        json=data
    )
    return r.status_code, r.json()


def find_building(data, base_url):
    if 'building_id' in data:
        building_id = data['building_id']
        if building_id is not None:
            print("match_by_building_id", building_id)
            return building_id

    if 'toid' in data:
        building_id = find_by_reference(base_url, 'toid', data['toid'])
        if building_id is not None:
            print("match_by_toid", data['toid'], building_id)
            return building_id

    if 'uprn' in data:
        building_id =  find_by_reference(base_url, 'uprn', data['uprn'])
        if building_id is not None:
            print("match_by_uprn", data['uprn'], building_id)
            return building_id

    print("no_match", data)
    return None


@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
def find_by_reference(base_url, ref_key, ref_id):
    """Find building_id by TOID or UPRN
    """
    r = requests.get("{}/api/buildings/reference".format(base_url), params={
        'key': ref_key,
        'id': ref_id
    })
    buildings = r.json()

    if buildings and 'error' not in buildings and len(buildings) == 1:
        building_id = buildings[0]['building_id']
    else:
        building_id = None

    return building_id

def parse_json_columns(row, json_columns):
    for col in json_columns:
        row[col] = json.loads(row[col])

    return row

if __name__ == '__main__':
    try:
        url, api_key, filename = sys.argv[1], sys.argv[2], sys.argv[3]
    except IndexError:
        print(
            "Usage: {} <URL> <api_key> ./path/to/data.csv [<json_columns>]".format(
            os.path.basename(__file__)
        ))
        exit()

    json_columns = sys.argv[4].split(',') if len(sys.argv) > 4 else []

    main(url, api_key, filename, json_columns)
