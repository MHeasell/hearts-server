import time

from redis import WatchError

from hearts.keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

from hearts.util import redis_key

from hearts.services.player import PlayerStateError, STATUS_QUEUING, STATUS_IN_GAME


class QueueService(object):

    def __init__(self, redis):
        self.redis = redis

    def add_player(self, player):
        stamp = time.time()

        player_key = redis_key("player", player)
        status_key = redis_key("player", player, "status")

        with self.redis.pipeline() as pipe:
            pipe.watch(player_key)
            pipe.watch(status_key)

            if pipe.get(player_key) is None:
                raise PlayerStateError("Player does not exist.")

            if pipe.get(status_key) == STATUS_IN_GAME:
                raise PlayerStateError("Player is currently in-game.")

            pipe.multi()
            pipe.set(status_key, STATUS_QUEUING)
            pipe.zadd(QUEUE_KEY, stamp, player)
            pipe.publish(QUEUE_CHANNEL_KEY, "player added")
            pipe.execute()

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
