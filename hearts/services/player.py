from uuid import uuid4

from redis import WatchError

from hearts.util import redis_key, ticket_key


class PlayerStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


class TicketService(object):

    def __init__(self, redis):
        self.redis = redis

    def get_player_from_ticket(self, ticket):
        return self.redis.get(ticket_key(ticket))

    def create_ticket_for(self, player):
        ticket = str(uuid4())
        self.redis.set(ticket_key(ticket), player)
        return ticket


class PlayerService(object):

    def __init__(self, redis):
        self.redis = redis

    def get_current_game(self, player):
        game_key = redis_key("player", player, "current_game")
        return self.redis.get(game_key)

    def create_player(self, player):
        player_key = redis_key("player", player)

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(player_key)

                    if pipe.get(player_key) is not None:
                        raise PlayerStateError("Player already exists.")

                    pipe.multi()
                    pipe.set(player_key, "1")
                    pipe.execute()
                    break
                except WatchError:
                    continue
