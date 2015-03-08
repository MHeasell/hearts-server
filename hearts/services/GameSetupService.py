import hearts.keys as keys
import json


class GameSetupService(object):

    def __init__(self, redis):
        self.redis = redis

    def add_game_setup_request(self, players):
        data = json.dumps({"players": players})
        self.redis.rpush(keys.GAME_SETUP_QUEUE_KEY, data

    def block_get_setup_request(self):
        data = self.redis.blpop(keys.GAME_SETUP_QUEUE_KEY)[1]
        return json.loads(data)
