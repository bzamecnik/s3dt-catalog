import heroku
import os

heroku_api_key = os.environ.get('HEROKU_API_KEY')
app_name = os.environ.get('HEROKU_APP_NAME')

client = heroku.from_key(heroku_api_key)

def ps_scale(ps_type, quantity):
    return client._http_resource(
        method='POST',
        resource=('apps', app_name, 'ps', 'scale'),
        data={'type': ps_type, 'qty': quantity})

def start_worker():
    return ps_scale('worker', 1)

def stop_worker():
    return ps_scale('worker', 0)

def worker_running():
    try:
        workers = client.apps[app_name].processes['worker']
        return True
    except KeyError:
        return False
