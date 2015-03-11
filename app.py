from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

import logging

import gevent

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
            raise APIError(419, "A player with this name already exists.")

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


@sockets.route("/play")
def connect_to_queue(ws):
    print "got connection"

    # auth
    ticket = ws.receive()
    if ticket is None:
        print "client bailed, exiting."
        return

    print "got ticket"

    player_id = ticket_svc.get_player_id(ticket)
    if player_id is None:
        print "ticket not valid, disconnecting"
        return  # disconnect un-authenticated users

    print "ticket is for user: " + str(player_id)

    game_id = game_backend.try_get_player_game(player_id)
    if game_id is None:
        _handle_queue_connection(ws, player_id)
    else:
        _handle_game_connection(ws, player_id, game_id)


def _handle_game_connection(ws, player_id, game_id):
    # send the game info
    evt_data = {
        "type": "game_found",
        "game_id": game_id
    }

    ws.send(json.dumps(evt_data))

    # TODO: write the real game protocol


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
