import os
import requests
from rq import Connection, get_current_job
import worker
import time

from ed_catalog import get_ed_catalog_url, download_ed_catalog_to_mongo, Counter
from shoptet_catalog import download_ed_catalog_to_mongo

# localhost if not defined
mongo_uri = os.environ.get('MONGOLAB_URI')

def update_ed_catalog():
    with Connection(worker.redis_client):
        start = time.time()
        job = get_current_job()
        login = os.environ.get('ED_LOGIN')
        password = os.environ.get('ED_PASSWORD')
        catalog_request_url = os.environ.get('ED_CATALOG_URI')
        catalog_url = get_ed_catalog_url(catalog_request_url, login, password)
        def counter_report(counter):
            job.meta['total_items'] = counter.total
            job.meta['selected_items'] = counter.selected
            job.save()
        counter = Counter(report=counter_report, report_period=1000)
        download_ed_catalog_to_mongo(mongo_uri, catalog_url, counter)

        end = time.time()
        job.meta['elapsed_time'] = '%.3f sec' % (end - start)
        job.save()

def update_shoptet_catalog():
    with Connection(worker.redis_client):
        start = time.time()
        job = get_current_job()

        catalog_url = os.environ.get('SHOPTET_CATALOG_URI')
        item_count = download_ed_catalog_to_mongo(mongo_uri, catalog_url)
        
        end = time.time()
        job.meta['elapsed_time'] = '%.3f sec' % (end - start)
        job.meta['total_items'] = item_count
        job.save()