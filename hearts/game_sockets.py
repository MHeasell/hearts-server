import json

import gevent
import gevent.queue as gq

from hearts.queue_backend import PlayerUnregisteredError
from hearts.model.exceptions import GameStateError


def send_ws_event(ws, event_type, data=None):
    if data is None:
        d = {"type": event_type}
    else:
        d = data.copy()
        d["type"] = event_type

    wire_str = json.dumps(d)
    ws.send(wire_str)
    print "sent: " + wire_str


def receive_ws_event(ws):
    data = ws.receive()
    if data is None:
        return None

    print "received: " + data
    return json.loads(data)


def send_command_fail(ws, command_id):
    send_ws_event(ws, "command_fail", {"command_id": command_id})


def send_command_success(ws, command_id):
    send_ws_event(ws, "command_success", {"command_id": command_id})


def consume_events(ws, event_queue):
    for item in event_queue:
        send_ws_event(ws, item[0], item[1])


def _serialize_game_state(game_info, player_index):
    game = game_info["game_object"]

    state = game.get_state()
    state_data = {}

    data = {
        "game_id": game_info["id"],
        "players": game_info["players"],
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
    elif state == "passing":
        state_data["round_number"] = game.get_current_round_number()
        state_data["hand"] = game.get_hand(player_index)
        state_data["pass_direction"] = game.get_pass_direction()
        state_data["have_passed"] = game.has_player_passed(player_index)
    else:
        raise Exception("Invalid game state: " + str(state))

    return data


def _handle_message(ws, game, player_idx, data):
    action = data["type"]
    command_id = data["command_id"]

    if action == "play_card":
        card = data["card"]
        try:
            if game.get_current_player() != player_idx:
                raise GameStateError()  # not this player's turn

            game.play_card(card)
        except GameStateError:
            send_command_fail(ws, command_id)

        send_command_success(ws, command_id)

    elif action == "pass_card":
        cards = data["cards"]
        if len(cards) != 3:
            raise Exception()  # must pass 3 cards

        try:
            game.pass_cards(player_idx, cards)
        except GameStateError:
            send_command_fail(ws, command_id)

        send_command_success(ws, command_id)

    else:
        print "received invalid message type: " + action
        send_command_fail(ws, command_id)


class GameWebsocketHandler(object):

    def __init__(self, ticket_svc, queue_backend, game_backend):
        self.ticket_svc = ticket_svc
        self.queue_backend = queue_backend
        self.game_backend = game_backend

    def handle_ws(self, ws):
        print "got connection"
        player_id = self._receive_auth(ws)
        if player_id is None:
            print "client bailed, exiting."
            return

        print "authenticated as user: " + str(player_id)

        game_id = self.game_backend.try_get_player_game(player_id)
        if game_id is None:
            self._handle_queue_connection(ws, player_id)
        else:
            self._handle_game_connection(ws, player_id, game_id)

    def _receive_auth(self, ws):
        while True:
            msg = receive_ws_event(ws)
            if msg is None:
                return None

            command_id = msg["command_id"]

            if msg.get("type") != "auth":
                print "got non-auth message, ignoring."
                send_command_fail(ws, command_id)

            print "got auth message"
            ticket = msg.get("ticket")
            if not ticket:
                print "got auth with no ticket, failing."
                send_command_fail(ws, command_id)
                continue

            player_id = self.ticket_svc.get_player_id(ticket)
            if player_id is None:
                print "ticket not valid"
                send_command_fail(ws, command_id)
                continue

            send_command_success(ws, command_id)
            return player_id

    def _handle_queue_connection(self, ws, player_id):
        # add to queue
        print "checking if user is already on the queue"
        if self.queue_backend.is_registered(player_id):
            print "player already in queue, disconnecting"
            return

        print "registering player in queue"
        result = self.queue_backend.register(player_id)

        # wait for cancel
        def check_cancel():
            while True:
                msg = ws.receive()
                if msg is None or msg == "cancel":
                    print "Client cancelled, unregistering."
                    self.queue_backend.unregister(player_id)
                    return

        listen_greenlet = gevent.spawn(check_cancel)

        try:
            game_id = result.get()
        except PlayerUnregisteredError:
            print "Player was unregistered, disconnecting."
            return

        listen_greenlet.kill()

        print "game found, handing over to game handler"

        self._handle_game_connection(ws, player_id, game_id)

    def _handle_game_connection(self, ws, player_id, game_id):
        # send the game state
        game_info = self.game_backend.get_game_info(game_id)
        player_idx = game_info["players"].index(player_id)

        send_ws_event(ws, "game_data", _serialize_game_state(game_info, player_idx))

        game = game_info["game_object"]
        event_queue = gq.Queue()
        observer = ConnectionObserver(game, player_idx, event_queue)
        game.add_observer(observer)

        queue_greenlet = gevent.spawn(consume_events, ws, event_queue)

        try:
            # listen for commands from the client
            while True:
                msg = receive_ws_event(ws)
                if msg is None:
                    print "player disconnected"
                    return
                else:
                    _handle_message(ws, game, player_idx, msg)
        finally:
            game.remove_observer(observer)
            queue_greenlet.kill()


class ConnectionObserver(object):
    def __init__(self, game, player_index, queue):
        self.game = game
        self.player_index = player_index
        self.queue = queue

    def on_start_round(self, round_number):
        hand = self.game.get_hand(self.player_index)

        data = {
            "round_number": round_number,
            "hand": hand
        }

        self._send_event("start_round", data)

    def on_finish_passing(self):
        cards = self.game.get_received_cards(self.player_index)

        data = {
            "received_cards": cards
        }

        self._send_event("finish_passing", data)

    def on_play_card(self, player_index, card):
        if player_index == self.player_index:
            # don't need to know about cards we played.
            return

        data = {
            "player": player_index,
            "card": card
        }

        self._send_event("play_card", data)

    def on_finish_trick(self, winner, points):
        pass

    def on_finish_round(self, scores):
        pass

    def _send_event(self, event_type, data):
        self.queue.put((event_type, data))
