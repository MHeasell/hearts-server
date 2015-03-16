import hearts.model.game as m
from hearts.game_master import GameMaster


class GameBackend(object):
    def __init__(self):
        self._next_game_id = 1
        self._game_masters = {}
        self._players = {}
        self._player_mapping = {}

    def create_game(self, players):
        game_id = self._next_game_id
        self._next_game_id += 1

        model = m.HeartsGame()
        model.start()

        master = GameMaster(model, game_id)
        self._game_masters[game_id] = master

        self._players[game_id] = list(players)

        for idx, player_id in enumerate(players):
            self._player_mapping[player_id] = (game_id, idx)

        return game_id

    def get_game_master(self, game_id):
        return self._game_masters[game_id]

    def try_get_player_game(self, player_id):
        data = self._player_mapping.get(player_id)
        if data is None:
            return None

        return data[0]

    def try_get_game_info(self, player_id):
        data = self._player_mapping.get(player_id)
        if data is None:
            return None

        return data

    def is_in_game(self, player_id):
        return player_id in self._player_mapping

    def on_game_finished(self, game_id):
        self._destruct_game(game_id)

    def on_game_abandoned(self, game_id):
        self._destruct_game(game_id)

    def _destruct_game(self, game_id):
        for player in self._players[game_id]:
            del self._player_mapping[player]

        del self._players[game_id]
        del self._game_masters[game_id]