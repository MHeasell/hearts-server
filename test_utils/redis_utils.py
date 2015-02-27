import redis

import subprocess

from time import sleep


def create_redis_test_process():
    redis_process = subprocess.Popen(
        ['redis-server', '--port', '7654'])
    sleep(1.0)
    return redis_process


def create_redis_test_connection():
    return redis.StrictRedis(host='localhost', port=7654, db=0)

