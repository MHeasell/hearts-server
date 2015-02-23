import time

from redis import WatchError

from hearts.keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

from hearts.util import redis_key

from hearts.services.player import PlayerStateError


class QueueService(object):

    def __init__(self, redis):
        self.redis = redis

    def get_status(self, player):
        game_key = redis_key("player", player, "current_game")
        with self.redis.pipeline() as pipe:
            pipe.zscore(QUEUE_KEY, player)
            pipe.get(game_key)
            queue_stamp, current_game = pipe.execute()

        if queue_stamp is not None:
            return "queuing", None

        if current_game is not None:
            return "in-game", current_game

        return "idle", None

    def add_player(self, player):
        stamp = time.time()

        player_key = redis_key("player", player)

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(player_key)

                    if pipe.get(player_key) is None:
                        raise PlayerStateError("Player does not exist.")

                    pipe.multi()
                    pipe.zadd(QUEUE_KEY, stamp, player)
                    pipe.publish(QUEUE_CHANNEL_KEY, "player added")
                    pipe.execute()

                    break

                except WatchError:
                    continue

    def try_get_players(self, count):
        return self.redis.zrange(QUEUE_KEY, 0, count - 1)
