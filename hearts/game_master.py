from hearts.model.exceptions import GameStateError
import gevent
import gevent.queue as gq
import hearts.websocket_util as wsutil


class PlayerAlreadyConnectedError(Exception):
    pass


def _consume_events(ws, queue):
        for item in queue:
            wsutil.send_ws_event(ws, item[0], item[1])


class GameMaster(object):
    def __init__(self, game, game_id):
        self._game_id = game_id
        self._game = game
        self._players = [None, None, None, None]
        self._observers = []

        game.add_observer(self)

    def add_observer(self, observer):
        self._observers.append(observer)

    def remove_observer(self, observer):
        self._observers.remove(observer)

    def connect(self, ws, player_id, player_index):
        if self._players[player_index] is not None:
            raise PlayerAlreadyConnectedError()

        queue = gq.Queue()
        queue_greenlet = gevent.spawn(_consume_events, ws, queue)
        self._players[player_index] = {
            "ws": ws,
            "id": player_id,
            "queue": queue,
        }

        wsutil.send_ws_event(ws, "connected_to_game")

        self._on_connect(player_index, player_id)

        try:
            while True:
                msg = wsutil.receive_ws_event(ws)
                if msg is None:
                    self._players[player_index] = None
                    self._on_disconnect(player_index)
                    return
                else:
                    self._receive_message(player_index, msg)
        finally:
            queue_greenlet.kill()

    def is_connected(self, player_index):
        return self._players[player_index] is not None

    def on_start_round(self, round_number):
        for idx, player in enumerate(self._players):
            if player is None:
                continue

            hand = self._game.get_hand(idx)

            data = {
                "round_number": round_number,
                "hand": hand
            }

            self._queue_event(idx, "start_round", data)

    def on_finish_passing(self):
        for idx, player in enumerate(self._players):
            if player is None:
                continue

            cards = self._game.get_received_cards(idx)

            data = {
                "received_cards": cards
            }

            self._queue_event(idx, "finish_passing", data)

    def on_play_card(self, player_index, card):
        data = {
            "player": player_index,
            "card": card
        }

        self._broadcast_event_from(player_index, "play_card", data)

    def on_finish_trick(self, winner, points):
        pass

    def on_finish_round(self, scores):
        # The client doesn't yet cope
        # with starting the next round immediately,
        # since it wants to wait to display the trick winner.
        # So, we wait some time for the client to do that
        # before starting the next round.
        gevent.spawn_later(2, self._continue_post_round)

    def on_finish_game(self):
        for obs in self._observers:
            obs.on_game_finished(self._game_id)

    def _continue_post_round(self):
        if self._game.is_player_above_hundred():
            self._game.end_game()
        else:
            self._game.start_next_round()

    def _receive_message(self, player_index, msg):
        data = msg
        game = self._game
        player_idx = player_index
        ws = self._players[player_index]["ws"]

        action = data["type"]
        command_id = data["command_id"]

        if action == "play_card":
            card = data["card"]
            try:
                if game.get_current_player() != player_idx:
                    raise GameStateError()  # not this player's turn

                game.play_card(card)
            except GameStateError:
                wsutil.send_command_fail(ws, command_id)
                return

            wsutil.send_command_success(ws, command_id)

        elif action == "pass_card":
            cards = data["cards"]
            try:
                game.pass_cards(player_idx, cards)
            except GameStateError:
                wsutil.send_command_fail(ws, command_id)
                return

            wsutil.send_command_success(ws, command_id)

        elif action == "get_state":
            state = self._serialize_game_state(player_index)
            wsutil.send_query_success(ws, command_id, state)

        else:
            print "received invalid message type: " + action
            wsutil.send_command_fail(ws, command_id)

    def _on_connect(self, player_index, player_id):
        data = {"index": player_index, "player": player_id}
        self._broadcast_event_from(player_index, "player_connected", data)

    def _on_disconnect(self, player_index):
        data = {"index": player_index}
        self._broadcast_event_from(player_index, "player_disconnected", data)

        if not any(self._players):
            self._on_all_disconnected()

    def _on_all_disconnected(self):
        if self._game.get_state() != "game_over":
            for obs in self._observers:
                obs.on_game_abandoned(self._game_id)

    def _queue_event(self, player_index, event_type, data):
        self._players[player_index]["queue"].put((event_type, data))

    def _broadcast_event(self, event_type, data):
        for player in self._players:
            if player is None:
                continue

            player["queue"].put((event_type, data))

    def _broadcast_event_from(self, origin_player_index, event_type, data):
        for idx, player in enumerate(self._players):
            if player is None:
                continue
            if idx == origin_player_index:
                continue

            player["queue"].put((event_type, data))

    def _serialize_player(self, player):
        if player is None:
            return None
        return player["id"]

    def _serialize_game_state(self, player_index):
        game = self._game

        state = game.get_state()
        state_data = {}

        data = {
            "game_id": self._game_id,
            "players": map(self._serialize_player, self._players),
            "scores": game.get_scores(),
            "state": state,
            "state_data": state_data
        }

        if state == "init":
            pass
        elif state == "game_over":
            pass
        elif state == "playing":
            state_data["round_number"] = game.get_current_round_number()
            state_data["hand"] = game.get_hand(player_index)
            state_data["trick"] = game.get_trick()
            state_data["current_player"] = game.get_current_player()
            state_data["round_scores"] = game.get_round_scores()
            state_data["is_hearts_broken"] = game.is_hearts_broken()
            state_data["is_first_trick"] = game.is_first_trick()
        elif state == "passing":
            state_data["round_number"] = game.get_current_round_number()
            state_data["hand"] = game.get_hand(player_index)
            state_data["pass_direction"] = game.get_pass_direction()
            state_data["have_passed"] = game.has_player_passed(player_index)
        else:
            raise Exception("Invalid game state: " + str(state))

        return data
