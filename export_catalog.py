"""
Export catalog from MongoDB to XML that can be imported to Shoptet.
"""

import argparse
import os
from collections import OrderedDict

import pymongo
import xmltodict
from pymongo import MongoClient


def export_catalog_from_mongo(item_collection, output_xml=None):
    """
    Exports items from ED that have been converted to Shoptet
    into and XML file.
    item_collection - MongoDB collection containing items
    output_xml - file-like where the XML will be written
    """
    items = item_collection.find({'shoptet_from_ed': {'$ne': None}}) \
        .sort('code', pymongo.ASCENDING)
    return export_catalog(items, output_xml)


def export_catalog(items, output_file):
    shop_items = [convert_item(item) for item in items]
    catalog_dict = OrderedDict([('SHOP', OrderedDict([('SHOPITEM', shop_items)]))])
    return xmltodict.unparse(catalog_dict, output=output_file, pretty=True)


def convert_item(item):
    converted_item = item['shoptet_from_ed']
    shoptet_item = item.get('shoptet')
    is_item_existent = shoptet_item is not None
    visible = shoptet_item['VISIBLE'] if is_item_existent else False
    visibility = 'visible' if visible else 'hidden'

    if is_item_existent:
        availability = (shoptet_item['AVAILABILITY_IN_STOCK']
                        if shoptet_item.get('AVAILABILITY_IN_STOCK') == 'Ihned k odeslání'
                        else converted_item['AVAILABILITY_IN_STOCK'])
        out_item = OrderedDict([
            ('CODE', converted_item['CODE']),
            # price might be updated by hand and should not be overwritten
            # ('PRICE', converted_item['PRICE']),
            # ('STANDARD_PRICE', converted_item['STANDARD_PRICE']),
            ('PURCHASE_PRICE', converted_item['PURCHASE_PRICE']),
            # the end-user price will be updated by hand, not overwritten
            # ('PRICE_VAT', converted_item['PRICE_VAT']),
            ('VAT', converted_item['VAT']),
            ('STOCK', converted_item['STOCK']),
            ('AVAILABILITY_IN_STOCK', availability),
            ('VISIBILITY', visibility)
        ])
    else:
        out_item = OrderedDict([
            ('NAME', converted_item['NAME']),
            ('DESCRIPTION', converted_item['DESCRIPTION']),
            ('MANUFACTURER', converted_item['MANUFACTURER']),
            ('WARRANTY', converted_item['WARRANTY']),
            ('ITEM_TYPE', converted_item['ITEM_TYPE']),
            ('UNIT', converted_item['UNIT']),
            ('IMAGES', converted_item['IMAGES']),
            ('FLAGS', converted_item['FLAGS']),
            ('CODE', converted_item['CODE']),
            ('PRICE', converted_item['PRICE']),
            ('STANDARD_PRICE', converted_item['STANDARD_PRICE']),
            ('PURCHASE_PRICE', converted_item['PURCHASE_PRICE']),
            ('PRICE_VAT', converted_item['PRICE_VAT']),
            ('VAT', converted_item['VAT']),
            ('EAN', converted_item['EAN']),
            ('CURRENCY', converted_item['CURRENCY']),
            ('STOCK', converted_item['STOCK']),
            ('AVAILABILITY_IN_STOCK', converted_item['AVAILABILITY_IN_STOCK']),
            ('AVAILABILITY_OUT_OF_STOCK', '14 dní'),
            ('VISIBILITY', visibility)
        ])
    return out_item


def export_catalog_xml():
    mongo_uri = os.environ.get('MONGO_URI')
    mongo = MongoClient(mongo_uri)
    db = mongo.get_default_database()
    item_collection = db.items
    return export_catalog_from_mongo(item_collection)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Export merged catalog from MongoDB to Shoptet XML.')
    parser.add_argument('output', help='Path to catalog in Shoptet XML format')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    mongo = MongoClient()
    db = mongo.s3dt_catalog
    item_collection = db.items

    with open(args.output, 'w') as output_xml_file:
        export_catalog_from_mongo(item_collection, output_xml_file)
