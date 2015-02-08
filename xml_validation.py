import argparse
from lxml import etree

def relax_ng_schema(schema_path):
    relaxng_doc = etree.parse(schema_path)
    return etree.RelaxNG(relaxng_doc)

def validate_relax_ng(doc_path, schema):
    doc = etree.parse(doc_path)
    
    schema.assertValid(doc)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Validate XML document using a RelaxNG schema.')
    parser.add_argument('doc', metavar='DOCUMENT', 
        help='Path to XML document to be validated')
    parser.add_argument('-s', '--schema',
        help='Path to RelaxNG schema')

    args = parser.parse_args()
    
    schema = relax_ng_schema(args.schema)
    try:
        validate_relax_ng(args.doc, schema)
        print('Document is valid.')
    except etree.DocumentInvalid as e:
        print('Document is NOT valid:', e)
        print(schema.error_log)
