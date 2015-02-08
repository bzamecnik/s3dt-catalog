"""
Flask Documentation:     http://flask.pocoo.org/docs/
Jinja2 Documentation:    http://jinja.pocoo.org/2/documentation/
Werkzeug Documentation:  http://werkzeug.pocoo.org/documentation/

This file creates your application.
"""

from io import BytesIO
import os
from flask import Flask, render_template, request, redirect, url_for, make_response
from lxml import etree
import requests
import xmltodict
from zipfile import ZipFile

# local modules
import catalog
import xml_validation

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY',
    'this should be set via an ENV variable')
app.config['ED_CONFIG'] = {
    'catalog_request_url': 'http://localhost:5000/ed_system_catalog_response_small_zip.xml',
    'login': os.environ.get('ED_LOGIN'),
    'password': os.environ.get('ED_PASSWORD')}

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
    catalog_res = requests.get(catalog_url)
    
    if not catalog_url.endswith('.zip'):
        catalog_xml = catalog_res.text
    else:
        zf = ZipFile(BytesIO(catalog_res.content))
        xml_file = zf.open(zf.filelist[0].filename, 'r')
        # TODO: try to process the catalog in the streaming mode
        catalog_xml = xml_file.read().decode()
    
    filter_enabled = request.form['filter'] == 'true'
    filtered_catalog = catalog.filter_catalog(catalog_xml) \
        if filter_enabled \
        else catalog_xml

    response = make_response(filtered_catalog)
    # TODO: add datetime to the file name
    response.headers["Content-Disposition"] = "attachment; filename=ed_catalog.xml"
    return response

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
    ed_catalog = request.files['ed_catalog_file']
    shoptet_catalog = catalog.convert_catalog(ed_catalog)
    response = make_response(shoptet_catalog)
    # TODO: add datetime to the file name
    response.headers["Content-Disposition"] = "attachment; filename=shoptet_catalog.xml"
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


@app.route('/download_shoptet/product_codes/')
def download_shoptet_existing_products():
    # url = 'http://localhost:5000/shoptet_catalog.xml'
    url = 'http://eshop.svet-3d-tisku.cz/export/productsSupplier.xml?visibility=-1&patternId=-4&hash=f1d6cd3ff3530f7b2caf569ee5cdc43346a397dd4baea81e8c5c7fa5d580fe51'
    catalog_res = requests.get(url, stream=True)    
    catalog_xml = catalog_res.text
    
    codes = []
    
    def parse_item(path, item, expected_path=['SHOP', 'SHOPITEM']):
        if [key for (key, value) in path] == expected_path:
            codes.append(item['CODE'])
            return True
    
    xmltodict.parse(catalog_xml, item_depth=2, item_callback=parse_item)
    
    response = make_response('\n'.join(codes))
    # TODO: add datetime to the file name
    response.headers["Content-Disposition"] = "attachment; filename=shoptet_catalog_codes.csv"
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


@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
