import hearts.model.game as m


class GameBackend(object):

    def __init__(self):
        self._next_game_id = 1
        self._games = {}
        self._players = {}
        self._player_mapping = {}

    def create_game(self, players):
        game_id = self._next_game_id
        self._next_game_id += 1

        model = m.HeartsGame()
        model.start()

        self._games[game_id] = model
        self._players[game_id] = players

        for idx, player_id in enumerate(players):
            self._player_mapping[player_id] = (game_id, idx)

        return game_id

    def get_players(self, game_id):
        return self._players[game_id]

    def get_player_index(self, game_id, player_id):
        players = self._players[game_id]
        return players.index(player_id)

    def try_get_player_game(self, player_id):
        data = self._player_mapping.get(player_id)
        if data is None:
            return None

        return data[0]

    def get_game(self, game_id):
        return self._games[game_id]

    def get_game_info(self, game_id):
        data = {
            "id": game_id,
            "game_object": self._games[game_id],
            "players": self._players[game_id]
        }

        return data
