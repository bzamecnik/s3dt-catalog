import argparse
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP
import re
import xmltodict

def read_file(path):
    with open(path, 'r') as file:
        return file.read()

def write_file(path, content):
    with open(path, 'w') as file:
        return file.write(content)

def read_file_as_xml_dict(path):
    return xmltodict.parse(read_file(path))

def boolean_to_integer(value):
    return "1" if value else "0"

def ean13_checksum(code):
    '''
    Adds the check digit to a EAN-12 code missing the check digit.
    code: 12 digit code without the check digit (string)
    returns: 13 digit code (string)
    
    It would work analogically for weights '131313131313'.
    '''
    weights = '131313131313'
    s = sum([int(c) * int(w) for (c, w) in zip(code, weights)])
    check_digit = ((10 - s) % 10) % 10
    return code + str(check_digit)

def ean14_to_ean_13(code):
    return ean13_checksum(code[1:-1])

def filter_catalog(input_xml):
    products = []
    out_dict = OrderedDict([('ResponseProductList', OrderedDict([('ProductList', products)]))])
    def handle_product(path, item, expected_path=['ResponseProductList', 'ProductList', 'Product']):
        # filter products from just a single category
        if [key for (key, value) in path] == expected_path and \
            (item['CommodityName'] == '3D TISK' or item['CommodityCode'] == '3DP'):
            products.append(OrderedDict([('Product', item)]))
        return True
    
    xmltodict.parse(input_xml, item_depth=3, item_callback=handle_product)
    
    out_dict['ResponseProductList']['GeneratedDate'] = get_generated_date(input_xml)
    
    output_xml = xmltodict.unparse(out_dict, pretty=True)
    return output_xml    

def get_generated_date(input_xml):
    l = [line for line in input_xml[-100:].splitlines(True) if 'GeneratedDate' in line][0].strip()
    return re.sub('.*<GeneratedDate>([^<]+)</GeneratedDate>.*', '\\1', l)

def convert_catalog(input_xml, existing_codes):
    shop_items = []
    out_dict = OrderedDict([('SHOP', OrderedDict([('SHOPITEM', shop_items)]))])
    
    existing_codes = set(existing_codes)

    def round_price(price):
        'Round price to 2 decimal places'
        return price.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    def add_vat(price, vat):
        return round_price(price * (Decimal('1') + vat))

    def handle_shop_item(path, item, expected_path=['ResponseProductList', 'ProductList', 'Product']):
        # also filter products from just a single category
        if [key for (key, value) in path] == expected_path and \
            (item['CommodityName'] == '3D TISK' or item['CommodityCode'] == '3DP'):
            
            endUserPrice = Decimal(item['EndUserPrice'])
            vatPercent = Decimal(item['Vat']).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            vat = Decimal('0.01') * vatPercent
            endUserPriceWithVat = add_vat(endUserPrice, vat)
            # Elinkx quantizes some stock amounts to ranges, eg. '10-49',
            # '50-99', '100+', also exact quantities are decimal, eg. '12,00'.
            # However, Shoptet only accepts exact integer amounts.
            # So we need to strip the decimal places and approximate the
            # integer amount, eg. by taking the  minimum if of the range.
            # Examples:
            # '12,00' -> '12'
            # '10-49' -> '10'
            # '100+' -> '100'
            stockItemCount = re.sub(r'([0-9]+)[,+-].*', '\\1', item['OnStockText'])
            
            # Shoptet only allows EAN-13, not EAN-14. Elinkx EAN codes might
            # have 13, 14 or even 6 digits. Longer codes are ignored.
            eanCode = item['EANCode']
            if not eanCode or len(eanCode) > 14:
                eanCode = ''
            elif len(eanCode) == 14:
                eanCode = ean14_to_ean_13(eanCode)
        
            availability = 'Externí sklad' if item['OnStock'] == 'true' else 'Není skladem'
        
            existing_item = item['Code'] in existing_codes
            if existing_item:
                out_item = OrderedDict([
                    ('CODE', item['Code']),
                    ('PRICE', item['EndUserPrice']),
                    ('STANDARD_PRICE', item['EndUserPrice']),
                    ('PURCHASE_PRICE', item['YourPriceWithFees']),
                    ('PRICE_VAT', endUserPriceWithVat),
                    ('VAT', vatPercent),
                    ('STOCK', OrderedDict([
                        ('AMOUNT', stockItemCount),
                        ('MINIMAL_AMOUNT', '0'), # ?
                    ])),
                ])
            else:
                out_item = OrderedDict([
                    ('NAME', item['Name']),
                    # ('SHORT_DESCRIPTION', ''), # ?
                    ('DESCRIPTION', item['Description']),
                    ('MANUFACTURER', item['ProducerName']),
                    # TODO: extract the number of moths as an integer
                    ('WARRANTY', item['Warranty']),
                    ('ITEM_TYPE', 'product'),
                    ('UNIT', 'ks'),
                    # optional
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
                    ('STANDARD_PRICE', item['EndUserPrice']),
                    ('PURCHASE_PRICE', item['YourPriceWithFees']),
                    ('PRICE_VAT', endUserPriceWithVat),
                    # weight is not given in the input data
                    # ('WEIGHT', '0'), # ?
                    ('VAT', vatPercent),
                    ('EAN', eanCode),
                    ('CURRENCY', 'CZK'), # ?
                    ('STOCK', OrderedDict([
                        ('AMOUNT', stockItemCount),
                        ('MINIMAL_AMOUNT', '0'), # ?
                    ])),
                    ('AVAILABILITY', availability),
                    ('VISIBILITY', 'hidden')
                ])
            shop_items.append(out_item)
            # shop_items.append(item) # just filter
        return True
    
    xmltodict.parse(input_xml, item_depth=3, item_callback=handle_shop_item)
    output_xml = xmltodict.unparse(out_dict, pretty=True)
    return output_xml

def test():
    input_path = 'resources/test/edsystem_catalog_small.xml'
    actual_output_path = 'resources/test/shoptet_catalog_small_actual.xml'
    expected_output_path = 'resources/test/shoptet_catalog_small_expected.xml'

    input_xml = read_file(input_path)
    actual_output_xml = convert_catalog(input_xml)
    print(actual_output_xml)
    write_file(actual_output_path, actual_output_xml)
    
    expected_output_xml = read_file(expected_output_path)
    
    assert actual_output_xml == expected_output_xml

def parse_args():
    parser = argparse.ArgumentParser(
        description='Converts ED Systems product feed XML to Shoptet format.')
    parser.add_argument('input', help='Path to catalog in ED Systems XML format')
    parser.add_argument('output', help='Path to catalog in Shoptet XML format')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    
    input_xml = read_file(args.input)
    output_xml = convert_catalog(input_xml)
    write_file(args.output, output_xml)
