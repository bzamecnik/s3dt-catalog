"""
Flask Documentation:     http://flask.pocoo.org/docs/
Jinja2 Documentation:    http://jinja.pocoo.org/2/documentation/
Werkzeug Documentation:  http://werkzeug.pocoo.org/documentation/
"""

import arrow
from collections import OrderedDict
from flask import Flask, render_template, redirect, url_for, make_response
import os
from pymongo import MongoClient
import redis
from rq import Queue, Connection
from rq.registry import FinishedJobRegistry, StartedJobRegistry
from rq_dashboard import RQDashboard
import worker

from export_catalog import export_catalog_xml
import tasks

app = Flask(__name__)

# Redis Queue dashboard, available at /rq/
# Make RQDashboard use the Redis-to-go service if available.

app.config['REDIS_URL'] = worker.redis_url
RQDashboard(app)

redis_client = worker.redis_client

@app.route('/')
def home():
    """Render website's home page."""
    return render_template('home.html')

@app.route('/catalog/ed', methods=['POST'])
def update_ed_catalog():
    with Connection(redis_client):
        q = Queue()
        result = q.enqueue(tasks.update_ed_catalog)
        return redirect(url_for('jobs'))

@app.route('/catalog/shoptet', methods=['POST'])
def update_shoptet_catalog():
    with Connection(redis_client):
        q = Queue()
        result = q.enqueue(tasks.update_shoptet_catalog)
        return redirect(url_for('jobs'))

@app.route('/catalog')
def export_catalog():
    catalog_xml = export_catalog_xml()
    response = make_response(catalog_xml)
    date = arrow.get().format('YYYY-MM-DD_HH-mm-ss')
    file_name = 'shoptet_catalog_import_%s.xml' % date
    response.headers["Content-Disposition"] = "attachment; filename=%s" % file_name
    return response

@app.route('/jobs/<job_id>')
def cancel_job(job_id):
    with Connection(redis_client):
        q = Queue()
        job = q.fetch_job(job_id)
        return render_template('job_details.html', job=job)

@app.route('/jobs/<job_id>/cancel')
def job_details(job_id):
    with Connection(redis_client):
        q = Queue()
        job = q.fetch_job(job_id)
        job.cancel()
        return redirect(url_for('jobs'))

@app.route('/jobs/')
def jobs():
    with Connection(redis_client):
        q = Queue()
        # possibly also use DeferredJobRegistry()
        jobs = OrderedDict([
            (name,
            [q.fetch_job(job_id) for job_id in registry.get_job_ids()]
            ) for (name, registry) in
            [('Waiting', q),
            ('Running', StartedJobRegistry()),
            ('Finished', FinishedJobRegistry()),
            ('Failed', Queue('failed'))]])
        return render_template('jobs.html', jobs=jobs)

@app.route('/<file_name>.zip')
def send_zip_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.zip'
    return app.send_static_file(file_dot_text)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
