import csv
from pymongo import MongoClient
import requests

def download_ed_catalog_to_mongo(mongo_uri, catalog_url):
    mongo = MongoClient(mongo_uri)
    db = mongo.s3dt_catalog
    item_collection = db.items
    item_collection.create_index("code")
    
    catalog_res = requests.get(catalog_url, stream=True)
    codes_csv = catalog_res.content.decode('cp1250')
    lines = codes_csv.split('\r\n')
    
    # input columns: code;pairCode;name;productVisibility;
    # output columns: CODE;VISIBLE
    item_count = 0
    for row in csv.reader(lines[1:], delimiter=';'):
        # product id, visibility
        if len(row) >= 3:
            item_count += 1
            item = {'CODE': row[0], 'VISIBLE': row[3] == 'visible'}
            item_collection.update(
                {'code': item['CODE']},
                {'$set': {'code': item['CODE'], 'shoptet': item}},
                upsert=True)
    
    return item_count