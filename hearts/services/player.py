from uuid import uuid4

from redis import WatchError

from hearts.util import redis_key, ticket_key, get_status_key, STATUS_IN_GAME, STATUS_QUEUING


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

    def get_status(self, player):
        status_key = redis_key("player", player, "status")
        game_key = redis_key("player", player, "current_game")

        with self.redis.pipeline() as pipe:
            pipe.get(status_key)
            pipe.get(game_key)
            return pipe.execute()

    def create_player(self, player):
        player_key = redis_key("player", player)
        status_key = redis_key("player", player, "status")

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(player_key)

                    if pipe.get(player_key) is not None:
                        raise PlayerStateError("Player already exists.")

                    pipe.multi()
                    pipe.set(player_key, "1")
                    pipe.set(status_key, "idle")
                    pipe.execute()
                    break
                except WatchError:
                    continue

    def set_as_in_game(self, game_id, *players):
        with self.redis.pipeline() as pipe:
            for player in players:
                status_key = get_status_key(player)
                pipe.set(status_key, STATUS_IN_GAME)
                pipe.set(redis_key("player", player, "current_game"), game_id)
                pipe.execute()