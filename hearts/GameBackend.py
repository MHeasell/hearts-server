import hearts.game_model as m


class GameBackend(object):

    def __init__(self):
        self._next_game_id = 1
        self._games = {}
        self._players = {}

    def create_game(self, players):
        game_id = self._next_game_id
        self._next_game_id += 1

        model = m.HeartsGame()

        self._games[game_id] = model
        self._players[game_id] = players

        return game_id

    def get_player_index(self, game_id, player_id):
        players = self._players[game_id]
        return players.index(player_id)

    def get_game(self, game_id):
        return self._games[game_id]
