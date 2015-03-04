import time

from hearts.keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

from hearts.util import retry_transaction


def _try_pop_players_transaction(pipe, count):
    pipe.watch(QUEUE_KEY)
    players = pipe.zrange(QUEUE_KEY, 0, count - 1)
    if len(players) < count:
        return None

    pipe.multi()
    pipe.zrem(QUEUE_KEY, *players)
    pipe.execute()

    return players


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
        players = retry_transaction(
            self.redis,
            _try_pop_players_transaction,
            count)

        if players is None:
            return None

        return map(int, players)
