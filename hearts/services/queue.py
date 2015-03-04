import time

from redis import WatchError

from hearts.keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

from hearts.util import redis_key

from hearts.services.player import PlayerStateError


class QueueService(object):

    def __init__(self, redis):
        self.redis = redis

    def add_player(self, player_id):
        stamp = time.time()

        with self.redis.pipeline() as pipe:
            pipe.zadd(QUEUE_KEY, stamp, player_id)
            pipe.publish(QUEUE_CHANNEL_KEY, "player added")
            pipe.execute()

    def try_pop_players(self, count):
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(QUEUE_KEY)
                    players = pipe.zrange(QUEUE_KEY, 0, count - 1)
                    if len(players) < count:
                        return None

                    pipe.multi()
                    pipe.zrem(QUEUE_KEY, *players)
                    pipe.execute()

                    return map(int, players)
                except WatchError:
                    continue
