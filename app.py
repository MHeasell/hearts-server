from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

import logging

import gevent
import gevent.queue as gq

import json

from flask import Flask, jsonify, abort, request
from flask_cors import CORS
from flask_sockets import Sockets


from redis import StrictRedis

from werkzeug.exceptions import default_exceptions, HTTPException

import ConfigParser

from hearts.services.ticket import TicketService
from hearts.services.player import PlayerService, PlayerStateError

from hearts.queue_backend import GameQueueBackend, PlayerUnregisteredError
from hearts.GameBackend import GameBackend

from hearts.model.exceptions import GameStateError

config = ConfigParser.RawConfigParser()
config.read('config.ini')

redis_host = config.get("Redis", "host")
redis_port = config.getint("Redis", "port")
redis_db = config.getint("Redis", "db")

use_cors = config.getboolean("Main", "use_cors")

app = Flask(__name__)

if use_cors:
    CORS(app)

sockets = Sockets(app)

redis = StrictRedis(host=redis_host, port=redis_port, db=redis_db)

ticket_svc = TicketService(redis)
player_svc = PlayerService(redis)

game_backend = GameBackend()
queue_backend = GameQueueBackend(game_backend)


class APIError(Exception):
    def __init__(self, status_code, message, **kwargs):
        self.status_code = status_code
        self.payload = kwargs
        self.payload["message"] = message

    def to_dict(self):
        return dict(self.payload)


def create_json_error(e):
    response = jsonify(message=str(e))
    if isinstance(e, HTTPException):
        response.status_code = e.code
    else:
        response.status_code = 500

    return response


for code in default_exceptions.iterkeys():
    app.error_handler_spec[None][code] = create_json_error


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


def find_requester_user_id():
    ticket = request.args.get("ticket", "")
    if not ticket:
        return None

    return ticket_svc.get_player_id(ticket)


def require_ticket_for(player):
    ticket = request.args.get("ticket", "")
    if ticket == "":
        abort(401)

    ticket_player = ticket_svc.get_player_id(ticket)
    if ticket_player != player:
        abort(403)


@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/players", methods=["POST"])
def users_resource():
    if request.method == "POST":
        name = request.form["name"]

        try:
            player_id = player_svc.create_player(name)
        except PlayerStateError:
            raise APIError(409, "A player with this name already exists.")

        ticket = ticket_svc.create_ticket_for(player_id)

        response = jsonify(id=player_id, name=name, ticket=ticket)
        response.status_code = 201
        return response


@app.route("/players/<int:player_id>")
def user_resource(player_id):
    data = player_svc.get_player(player_id)
    if data is None:
        raise APIError(404, "Player not found.")

    return jsonify(id=data["id"], name=data["name"], current_game=data["current_game"])


def receive_auth(ws):
    while True:
        msg = receive_ws_event(ws)
        if msg is None:
            return None

        if msg.get("type") != "auth":
            print "got non-auth message, ignoring."
            continue

        print "got auth message"
        ticket = msg.get("ticket")
        if not ticket:
            print "got auth with no ticket, failing."
            send_ws_event(ws, "auth_fail")
            continue

        player_id = ticket_svc.get_player_id(ticket)
        if player_id is None:
            print "ticket not valid"
            send_ws_event(ws, "auth_fail")
            continue

        send_ws_event(ws, "auth_success")
        return player_id


@sockets.route("/play")
def connect_to_queue(ws):
    print "got connection"

    player_id = receive_auth(ws)
    if player_id is None:
        print "client bailed, exiting."
        return

    print "authenticated as user: " + str(player_id)

    game_id = game_backend.try_get_player_game(player_id)
    if game_id is None:
        _handle_queue_connection(ws, player_id)
    else:
        _handle_game_connection(ws, player_id, game_id)


def _handle_message(ws, game, player_idx, data):
    action = data["type"]

    if action == "play_card":
        card = data["card"]
        try:
            if game.get_current_player() != player_idx:
                raise GameStateError()  # not this player's turn

            game.play_card(card)
        except GameStateError:
            send_ws_event(ws, "command_fail")

        send_ws_event(ws, "command_success")

    elif action == "pass_card":
        cards = data["cards"]
        if len(cards) != 3:
            raise Exception()  # must pass 3 cards

        try:
            game.pass_cards(player_idx, cards)
        except GameStateError:
            send_ws_event(ws, "command_fail")

        send_ws_event(ws, "command_success")

    else:
        print "received invalid message type: " + action
        send_ws_event(ws, "command_fail")


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
    elif state == "playing":
        state_data["hand"] = game.get_hand(player_index)
        state_data["trick"] = game.get_trick()
        state_data["current_player"] = game.get_current_player()
        state_data["round_scores"] = game.get_round_scores()
        state_data["is_hearts_broken"] = game.is_hearts_broken()
    elif state == "passing":
        state_data["hand"] = game.get_hand(player_index)
        state_data["pass_direction"] = game.get_pass_direction()
        state_data["have_passed"] = game.has_player_passed(player_index)
    else:
        raise Exception("Invalid game state: " + str(state))

    return data


class ConnectionObserver(object):
    def __init__(self, game, player_index, queue):
        self.game = game
        self.player_index = player_index
        self.queue = queue

    def on_start(self):
        pass

    def on_start_preround(self, pass_direction):
        hand = self.game.get_hand(self.player_index)

        data = {
            "pass_direction": pass_direction,
            "hand": hand
        }

        self._send_event("start_preround", data)

    def on_finish_preround(self):
        cards = self.game.get_received_cards(self.player_index)

        data = {
            "received_cards": cards
        }

        self._send_event("finish_preround", data)

    def on_start_playing(self):
        hand = self.game.get_hand(self.player_index)

        data = {
            "hand": hand
        }

        self._send_event("start_playing", data)

    def on_play_card(self, player_index, card):
        data = {
            "player": player_index,
            "card": card
        }

        self._send_event("play_card", data)

    def on_finish_trick(self, winner, points):
        data = {
            "winner": winner,
            "points": points
        }

        self._send_event("finish_trick", data)

    def _send_event(self, event_type, data):
        self.queue.put((event_type, data))


def _handle_game_connection(ws, player_id, game_id):
    # send the game state
    game_info = game_backend.get_game_info(game_id)
    player_idx = game_info["players"].index(player_id)

    send_ws_event(ws, "game_data", _serialize_game_state(game_info, player_idx))

    game = game_info["game_object"]
    event_queue = gq.Queue()
    observer = ConnectionObserver(game, player_idx, event_queue)
    game.add_observer(observer)

    def consume_events():
        for item in event_queue:
            send_ws_event(ws, item[0], item[1])

    queue_greenlet = gevent.spawn()

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


def _handle_queue_connection(ws, player_id):
    # add to queue
    print "checking if user is already on the queue"
    if queue_backend.is_registered(player_id):
        print "player already in queue, disconnecting"
        return

    print "registering player in queue"
    result = queue_backend.register(player_id)

    # wait for cancel
    def check_cancel():
        while True:
            msg = ws.receive()
            if msg is None or msg == "cancel":
                print "Client cancelled, unregistering."
                queue_backend.unregister(player_id)
                return

            gevent.sleep()

    listen_greenlet = gevent.spawn(check_cancel)

    try:
        game_id = result.get()
    except PlayerUnregisteredError:
        print "Player was unregistered, disconnecting."
        return

    listen_greenlet.kill()

    print "game found, handing over to game handler"

    _handle_game_connection(ws, player_id, game_id)


if __name__ == "__main__":
    l = logging.getLogger('cocks')
    l.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    l.addHandler(ch)

    app.debug = True

    server = WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    server.logger = l

    server.serve_forever()
