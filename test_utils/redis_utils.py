import redis

import subprocess

import os

import random

from time import sleep


class RedisTestService(object):

    def __init__(self):
        self._port = random.randint(49152, 65535)
        self._proc = subprocess.Popen(
            ['redis-server', '--port', str(self._port)],
            stdout=open(os.devnull, 'wb'))
        sleep(0.2)

    def create_connection(self):
        return redis.StrictRedis(host='localhost', port=self._port, db=0)

    def close(self):
        self._proc.terminate()
