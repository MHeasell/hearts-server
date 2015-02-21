import time

from redis import WatchError

from hearts.keys import QUEUE_KEY, QUEUE_CHANNEL_KEY


class QueueService(object):

    def __init__(self, redis):
        self.redis = redis

    def add_player(self, player):
        stamp = time.time()
        with self.redis.pipeline() as pipe:
            pipe.zadd(QUEUE_KEY, stamp, player)
            pipe.publish(QUEUE_CHANNEL_KEY, "player added")
            pipe.execute()

    def contains_player(self, player):
        return self.redis.zscore(player) is not None

    def try_get_players(self, count):
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(QUEUE_KEY)

                    queue_length = pipe.zcard(QUEUE_KEY)
                    if queue_length < count:
                        return None

                    players = pipe.zrange(QUEUE_KEY, 0, count - 1)

                    pipe.multi()

                    for player in players:
                        pipe.zrem(QUEUE_KEY, player)

                    pipe.execute()

                    return players

                except WatchError:
                    continue
