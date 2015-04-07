"""
Flask Documentation:     http://flask.pocoo.org/docs/
Jinja2 Documentation:    http://jinja.pocoo.org/2/documentation/
Werkzeug Documentation:  http://werkzeug.pocoo.org/documentation/

This file creates your application.
"""

import csv
from flask import Flask, render_template, request, redirect, make_response
from io import BytesIO, StringIO
from lxml import etree
import os
import pandas as pd
import re
import requests
from werkzeug.contrib.iterio import IterIO
from werkzeug.datastructures import Headers
from werkzeug.wsgi import wrap_file
import xmltodict
from zipfile import ZipFile

# local modules
import catalog
import xml_validation

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY',
    'this should be set via an ENV variable')
app.config['ED_CONFIG'] = {
    # 'catalog_request_url': 'http://localhost:5000/ed_system_catalog_response_zip.xml',
    'catalog_request_url': 'http://public.ws.cz.elinkx.biz/service.asmx/getProductListDownloadZIP',
    'login': os.environ.get('ED_LOGIN'),
    'password': os.environ.get('ED_PASSWORD')}
app.config['SHOPTET_CONFIG'] = {
     # 'existing_products_url': 'http://localhost:5000/shoptet_product_codes.csv',
    'existing_products_url': 'http://eshop.svet-3d-tisku.cz/export/products.csv?visibility=-1&patternId=2&hash=a2106697936ebe62acc68776868370732a89984fd7f48ac348f0e33cd3837489',
}

###
# Routing for your application.
###

@app.route('/')
def home():
    """Render website's home page."""
    return render_template('home.html')

@app.route('/download_ed/', methods=['POST'])
def download_ed_catalog():
#     response_xml = '''<?xml version="1.0" encoding="utf-8"?>
# <ResponseProductListStatus xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.elinkx.cz">
#   <Status>
#     <StatusCode>DONE</StatusCode>
#     <ErrorText />
#   </Status>
#   <ProductListStatus>
#     <url>http://public.ws.cz.elinkx.biz/download/priceList_1055541_UTF8_72d69218-5a07-4654-970d-eaedbc0a56e8.zip</url>
#     <fileName>priceList_1055541_UTF8_72d69218-5a07-4654-970d-eaedbc0a56e8.zip</fileName>
#     <isReady>true</isReady>
#   </ProductListStatus>
# </ResponseProductListStatus>'''
    catalog_url = get_ed_catalog_url()
    catalog_res = requests.get(catalog_url, stream=True)
    
    # Read the request content, zip file and XML file via a stream to prevent
    # reading the whole data into memory at once. The memory used should be
    # constant regardless of the size of the input data.
    if not catalog_url.endswith('.zip'):
        catalog_xml = IterIO(catalog_res.iter_lines)
    else:
        with ZipFile(IterIO(catalog_res.iter_content(chunk_size=4096), sentinel=b'')) as zf:
            with zf.open(zf.filelist[0].filename, 'r') as xml_file:
                catalog_xml = xml_file
    
    filter_enabled = request.form['filter'] == 'true'
    filtered_catalog = catalog.filter_catalog(catalog_xml) \
        if filter_enabled \
        else catalog_xml

    # TODO: add datetime to the file name
    headers = Headers()
    headers.add("Content-Disposition", "attachment; filename=ed_catalog.xml")
    # allow the output file to be streamed
    return Response(wrap_file(environ, filtered_catalog),
        direct_passthrough=True,
        headers=headers)

def get_ed_catalog_url():
    ed_config = app.config['ED_CONFIG']
    catalog_request_url = ed_config['catalog_request_url']
    params = {
        'login': ed_config['login'],
        'password': ed_config['password'],
        'encoding': 'UTF-8',
        'onStock': 'False'}
    res = requests.get(catalog_request_url, params=params)
    response_xml = xmltodict.parse(res.text)
    plStatus = response_xml['ResponseProductListStatus']['ProductListStatus']
    catalog_url = plStatus['url']
    return catalog_url

@app.route('/convert_ed_to_shoptet/', methods=['POST'])
def convert_catalog():
    # required
    ed_catalog = request.files['ed_catalog_file']
    # optional - if not given all products are treated as new
    shoptet_catalog_file = request.files['shoptet_catalog_file']
    shoptet_existing_items = shoptet_catalog_file.read().decode()
    
    if len(shoptet_existing_items) > 0:
        df = pd.read_csv(StringIO(shoptet_existing_items),
            dtype={'product_code': str, 'visible': bool})
        df.set_index('product_code', inplace=True)
    else:
        df = pd.DataFrame()
    
    shoptet_catalog = catalog.convert_catalog(ed_catalog, df)
    response = make_response(shoptet_catalog)
    # TODO: add datetime to the file name
    response.headers["Content-Disposition"] = "attachment; filename=shoptet_catalog_import.xml"
    return response

@app.route('/validate_shoptet/', methods=['POST'])
def validate_shoptet_catalog():
    doc = request.files['input_file']
    file_name = doc.filename
    schema = xml_validation.relax_ng_schema('resources/products-supplier-v10.rng')
    try:
        xml_validation.validate_relax_ng(doc, schema)
        is_valid, log, exception = True, None, None
    except etree.DocumentInvalid as e:
        is_valid, log, exception = False, schema.error_log, e
    
    return render_template('validate_shoptet.html',
        file_name=file_name, is_valid=is_valid, exception=exception, log=log)

@app.route('/download_shoptet/existing_catalog/')
def download_shoptet_existing_products():
    '''
    Converts one CSV file to another.
    '''
    # example excerpt of the input CSV file (cp1250, CR-LF, quotes):
    #
    # code;pairCode;name;productVisibility;
    # "0001";;"3D tiskarna Profi3DMaker tryska ? 0,5mm / 3D Printer 0,5 mm";"visible";
    #
    # example output CSV (UTF-8, LF, no-quotes):
    # product_code,visible
    # 0001,true
    
    url = app.config['SHOPTET_CONFIG']['existing_products_url']
    catalog_res = requests.get(url, stream=True)
    codes_csv = catalog_res.content.decode('cp1250')
    lines = codes_csv.split('\r\n')
    
    existing_products = StringIO()
    csvwriter = csv.writer(existing_products)
    csvwriter.writerow(['product_code', 'visible'])

    # input columns: code;pairCode;name;productVisibility;
    # output columns: product_code,visible
    for row in csv.reader(lines[1:], delimiter=';'):
        # product id, visibility
        if len(row) >= 3:
            csvwriter.writerow([row[0], str(row[3] == 'visible').lower()])

    response = make_response(existing_products.getvalue())
    # TODO: add datetime to the file name
    response.headers["Content-Disposition"] = "attachment; filename=shoptet_existing_catalog.csv"
    return response

@app.route('/<file_name>.xml')
def send_xml_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.xml'
    return app.send_static_file(file_dot_text)

@app.route('/<file_name>.zip')
def send_zip_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.zip'
    return app.send_static_file(file_dot_text)


@app.route('/<file_name>.csv')
def send_csv_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.csv'
    return app.send_static_file(file_dot_text)

@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
