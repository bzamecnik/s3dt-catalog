'''
Runs a background Redis-based job queue worker that processes incoming jobs.

It connects either to redis running at the Redis-to-go or at the localhost.

See https://devcenter.heroku.com/articles/python-rq for more information.
'''

import os
import redis
from rq import Queue, Worker, Connection

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

redis_client = redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(redis_client):
        worker = Worker(Queue())
        worker.work()
