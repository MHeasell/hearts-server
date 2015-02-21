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

    def player_exists(self, player):
        key = redis_key("player", player)
        return self.redis.get(key) is not None

    def get_status(self, player):
        key = redis_key("player", player, "status")
        return self.redis.get(key)

    def set_status(self, player):
        key = redis_key("player", player, "status")
        self.redis.set(key)

    def get_current_game_id(self, player):
        key = redis_key("player", player, "current_game")
        return self.redis.get(key)

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

    def set_as_queuing(self, player):
        status_key = redis_key("player", player, "status")

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(status_key)
                    status = pipe.get(status_key)
                    if status == STATUS_IN_GAME:
                        raise PlayerStateError(player + " is currently in-game.")

                    pipe.multi()
                    pipe.set(status_key, STATUS_QUEUING)
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