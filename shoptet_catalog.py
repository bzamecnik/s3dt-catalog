import csv

import requests
from pymongo import MongoClient


def download_shoptet_catalog_to_mongo(mongo_uri, catalog_url):
    catalog_str = download_shoptet_catalog(catalog_url)
    items = parse_catalog_csv(catalog_str)
    update_items_in_mongo(items, mongo_uri)
    return len(items)


def download_shoptet_catalog(catalog_url):
    """
    Downloads the catalog CSV from Shoptet, decodes it and returns the string.
    """
    response = requests.get(catalog_url)
    return response.content.decode('cp1250')


def parse_catalog_csv(catalog_csv_str):
    """
    Parses the CSV into a list of items (each is a dict).
    """
    lines = catalog_csv_str.split('\r\n')

    # input columns: code;pairCode;name;productVisibility;
    # output columns: CODE;VISIBLE
    columns = lines[0].strip().split(';')
    codeIndex = columns.index('code')
    visibilityIndex = columns.index('productVisibility')
    availabilityInStockIndex = columns.index('availabilityInStock')

    # we extract product id, visibility
    return [
        {
            'CODE': row[codeIndex],
            'VISIBLE': row[visibilityIndex] == 'visible',
            'AVAILABILITY_IN_STOCK': row[availabilityInStockIndex]
        }
        for row in csv.reader(lines[1:], delimiter=';')
        if len(row) >= 4
    ]


def update_items_in_mongo(items, mongo_uri):
    mongo = MongoClient(mongo_uri)
    db = mongo.get_default_database()
    item_collection = db.items
    item_collection.create_index("code")

    item_count = 0

    for item in items:
        item_count += 1
        item_collection.update(
            {'code': item['CODE']},
            {'$set': {'code': item['CODE'], 'shoptet': item}},
            upsert=True)

    return item_count
