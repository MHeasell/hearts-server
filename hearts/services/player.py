from redis import WatchError

from hearts.util import player_key


class PlayerStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


class PlayerService(object):

    def __init__(self, redis):
        self.redis = redis

    def get_player(self, player_id):
        key = player_key(player_id)
        data = self.redis.hgetall(key)
        if data is None:
            return None

        data["id"] = int(data["id"])

        return data

    def get_player_id(self, name):
        player_id = self.redis.hget("usernames", name)
        if player_id is None:
            return None

        return int(player_id)

    def get_player_by_name(self, name):
        player_id = self.get_player_id(name)

        if player_id is None:
            return None

        return self.get_player(player_id)

    def create_player(self, name):
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch("usernames", "next_player_id")

                    existing_id = self.redis.hget("usernames", name)

                    if existing_id is not None:
                        raise PlayerStateError("Player already exists.")

                    player_id = int(self.redis.get("next_player_id") or "1")

                    key = player_key(player_id)

                    player_map = {
                        "id": player_id,
                        "name": name,
                        "status": "idle"
                    }

                    pipe.multi()
                    pipe.hset("usernames", name, player_id)
                    pipe.hmset(key, player_map)
                    pipe.set("next_player_id", player_id + 1)
                    pipe.execute()
                    return player_id
                except WatchError:
                    continue
