from gevent.event import AsyncResult


class PlayerUnregisteredError(Exception):
    pass


class GameQueueBackend(object):
    def __init__(self, game_creator):
        self.clients = []
        self.game_creator = game_creator

    def register(self, player_id):
        result = AsyncResult()
        self.clients.append((player_id, result))

        self.try_match()

        return result

    def try_match(self):
        if len(self.clients) < 4:
            return

        players = self.clients[:4]
        self.clients = self.clients[4:]

        player_ids = map(lambda x: x[0], players)
        game_id = self.game_creator.create_game(player_ids)

        for _, result in players:
            result.set(game_id)

    def is_registered(self, player_id):
        for idx, (item_id, _) in enumerate(self.clients):
            if item_id == player_id:
                return True

        return False

    def unregister(self, player_id):
        found_idx = None
        for idx, (item_id, _) in enumerate(self.clients):
            if item_id == player_id:
                found_idx = idx
                break

        if found_idx is not None:
            _, result = self.clients.pop(found_idx)
            result.set_exception(PlayerUnregisteredError())
