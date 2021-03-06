import os
import re
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP
from zipfile import ZipFile

import requests
import xmltodict
from pymongo import MongoClient
from werkzeug.contrib.iterio import IterIO


def download_ed_catalog(catalog_url):
    print('download_ed_catalog({})', catalog_url)
    catalog_res = requests.get(catalog_url, stream=True)
    print('response: {}', catalog_res)

    # Read the request content, zip file and XML file via a stream to prevent
    # reading the whole data into memory at once. The memory used should be
    # constant regardless of the size of the input data.
    if not catalog_url.endswith('.zip'):
        catalog_xml = IterIO(catalog_res.iter_lines)
    else:
        with ZipFile(IterIO(catalog_res.iter_content(chunk_size=4096), sentinel=b'')) as zf:
            with zf.open(zf.filelist[0].filename, 'r') as xml_file:
                catalog_xml = xml_file
    return catalog_xml


def get_ed_catalog_url(catalog_request_url, login, password):
    params = {
        'login': login,
        'password': password,
        'encoding': 'UTF-8',
        'onStock': 'False'}
    res = requests.get(catalog_request_url, params=params)
    print(res.text)
    response_xml = xmltodict.parse(res.text)
    pl_status = response_xml['ResponseProductListStatus']['ProductListStatus']
    catalog_url = pl_status['url']
    return catalog_url


def process_catalog(input_xml, process_item):
    print('process_catalog()')
    '''
    Processes each product item from an ED catalog XML in a streamed way.
    input_xml - a string or stream representing the XML
    process_item - a function to be called for each item (OrderedDict)
    '''

    expected_path = ['ResponseProductList', 'ProductList', 'Product']

    def handle_item(path, item):
        if [key for (key, value) in path] == expected_path:
            process_item(item)
        return True

    xmltodict.parse(input_xml, item_depth=3, item_callback=handle_item)


def is_3d_print_item(item):
    """Filters products from just a single category"""
    return item['CommodityName'] == '3D TISK' or item['CommodityCode'] == '3DP'


def update_item_to_mongo(ed_item, collection):
    # NOTE: upsert is much slower than insert, but we'd like to
    # store also items from Shoptet in the same collection
    print('updating item', ed_item['Code'])
    shoptet_item = convert_item(ed_item)
    collection.update(
        {'code': ed_item['Code']},
        {'$set': {
            'code': ed_item['Code'],
            'ed': ed_item,
            'shoptet_from_ed': shoptet_item}},
        upsert=True)


def load_catalog_to_mongo(input_xml, item_collection, counter):
    def process_item(item):
        counter.item_visited()
        if is_3d_print_item(item):
            counter.item_selected()
            update_item_to_mongo(item, item_collection)

    process_catalog(input_xml, process_item)
    counter.finished()


def convert_item(item):
    """Converts an item from ED format to Shoptet format"""

    end_user_price = Decimal(item['EndUserPrice'])
    vat_percent = Decimal(item['Vat']).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP)
    vat = Decimal('0.01') * vat_percent
    end_user_price_with_vat = add_vat(end_user_price, vat)

    # purchase price without VAT
    purchase_price = Decimal(item['YourPriceWithFees'])
    purchase_price_with_vat = add_vat(purchase_price, vat)

    # ED quantizes some stock amounts to ranges, eg. '10-49',
    # '50-99', '100+', also exact quantities are decimal, eg. '12,00'.
    # However, Shoptet only accepts exact integer amounts.
    # So we need to strip the decimal places and approximate the
    # integer amount, eg. by taking the  minimum if of the range.
    # Examples:
    # '12,00' -> '12'
    # '10-49' -> '10'
    # '100+' -> '100'
    stock_item_count = re.sub(r'([0-9]+)[,+-].*', '\\1', item['OnStockText'])

    # Shoptet only allows EAN-13, not EAN-14. ED EAN codes might
    # have 13, 14 or even 6 digits. Longer codes are ignored.
    ean_code = item['EANCode']
    if not ean_code or len(ean_code) > 14:
        # some dummy EAN code (note that checksum of 12*'0' is 0)
        ean_code = 13 * '0'
    elif len(ean_code) == 14:
        ean_code = ean14_to_ean_13(ean_code)

    def get_description(item):
        # DESCRIPTION must not be empty, so we can fall back to NAME
        if item['Description'] and len(item['Description']) > 0:
            return item['Description']
        else:
            return item['Name']

    out_item = OrderedDict([
        ('NAME', item['Name']),
        # ('SHORT_DESCRIPTION', ''), # ?
        ('DESCRIPTION', get_description(item)),
        ('MANUFACTURER', item['ProducerName']),
        ('WARRANTY', item['Warranty']),
        ('ITEM_TYPE', 'product'),
        ('UNIT', 'ks'),
        # optional:
        # ('CATEGORIES', OrderedDict([('CATEGORY', item['CommodityName'])])),
        ('IMAGES', OrderedDict([('IMAGE', item['ImageUrl'])])),
        ('FLAGS', OrderedDict([
            ('ACTION', boolean_to_integer(item['Status'] == 'Doprodej')),
            ('NEW', boolean_to_integer(item['Status'] == 'Novinka')),
            ('TIP', boolean_to_integer(item['Status'] == 'TOP Produkt')),
        ])),
        ('CODE', item['Code']),
        ('PRICE', item['EndUserPrice']),
        # end user price in case of some discount
        ('STANDARD_PRICE', str(end_user_price_with_vat)),
        ('PURCHASE_PRICE', str(purchase_price_with_vat)),
        ('PRICE_VAT', str(end_user_price_with_vat)),
        # weight is not given in the input data
        # ('WEIGHT', '0'), # ?
        ('VAT', str(vat_percent)),
        ('EAN', ean_code),
        ('CURRENCY', 'CZK'),  # ?
        ('STOCK', OrderedDict([
            ('AMOUNT', stock_item_count),
            ('MINIMAL_AMOUNT', '0'),  # ?
        ])),
        ('AVAILABILITY_IN_STOCK', 'Skladem u dodavatele' if item['OnStock'] == 'true' else 'Není skladem')
    ])
    return out_item


def round_price(price):
    """Round price to 2 decimal places"""
    return price.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def add_vat(price, vat):
    return round_price(price * (Decimal('1') + vat))


def boolean_to_integer(value):
    return '1' if value else '0'


def ean13_checksum(code):
    """
    Adds the check digit to a EAN-12 code missing the check digit.
    code: 12 digit code without the check digit (string)
    returns: 13 digit code (string)

    It would work analogically for weights '131313131313'.
    """
    weights = '131313131313'
    s = sum([int(c) * int(w) for (c, w) in zip(code, weights)])
    check_digit = ((10 - s) % 10) % 10
    return code + str(check_digit)


def ean14_to_ean_13(code):
    return ean13_checksum(code[1:-1])


def download_ed_catalog_to_mongo(mongo_uri, catalog_url, counter):
    mongo = MongoClient(mongo_uri)
    db = mongo.get_default_database()
    item_collection = db.items
    item_collection.create_index('code')

    catalog_xml = download_ed_catalog(catalog_url)
    load_catalog_to_mongo(catalog_xml, item_collection, counter)


class Counter(object):
    def __init__(self, report=None, report_period=1000):
        self.total = 0
        self.selected = 0
        self.report_period = report_period
        self.report = report

    def item_visited(self):
        self.total += 1
        if self.report and self.total % self.report_period == 0:
            self.report(self)

    def item_selected(self):
        self.selected += 1

    def finished(self):
        self.report(self)


if __name__ == '__main__':
    def ed_catalog_url():
        # catalog_request_url = 'http://public.ws.cz.elinkx.biz/service.asmx/getProductListDownloadZIP'
        # catalog_url = get_ed_catalog_url(catalog_request_url)
        catalog_url = 'http://localhost:5000/static/priceList_1055541_UTF8_63e3bbe9-ab87-49bf-a221-b20590b106de.zip'
        return catalog_url

    mongo_uri = os.environ.get('MONGO_URI')  # localhost if not defined

    def counter_report(counter):
        print('total:', counter.total, ', selected:', counter.selected)

    counter = Counter(report=counter_report, report_period=1000)
    download_ed_catalog_to_mongo(mongo_uri, ed_catalog_url(), counter)
