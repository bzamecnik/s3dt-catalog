web: gunicorn -b "0.0.0.0:${WEB_PORT}" app:app --log-file -
worker: python -u worker.py
