from passlib.apps import custom_app_context as pwd_context


class PlayerStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


class PlayerExistsError(PlayerStateError):
    pass


class PlayerService(object):

    def __init__(self):
        self._players = {}
        self._usernames = {}
        self._next_id = 1

    def get_player(self, player_id):
        data = self._players.get(player_id)
        if data is None:
            return None

        out_data = {
            "id": int(data["id"]),
            "name": data["name"]
        }

        return out_data

    def get_player_id(self, name):
        return self._usernames.get(name)

    def get_player_by_name(self, name):
        player_id = self.get_player_id(name)

        if player_id is None:
            return None

        return self.get_player(player_id)

    def create_player(self, name, password):
        if name in self._usernames:
            raise PlayerExistsError()

        password_hash = pwd_context.encrypt(password)

        player_id = self._next_id
        self._next_id += 1

        self._players[player_id] = {
            "id": player_id,
            "name": name,
            "password_hash": password_hash
        }

        self._usernames[name] = player_id

        return player_id

    def auth_player(self, player_id, password):
        player = self._players.get(player_id)
        if player is None:
            return False

        pwd_hash = player["password_hash"]
        return pwd_context.verify(password, pwd_hash)

    def remove_player(self, player_id):
        name = self._players[player_id]["name"]
        del self._usernames[name]
        del self._players[player_id]
