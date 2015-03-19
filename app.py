from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

import logging

from flask import Flask, jsonify, abort, request
from flask_sockets import Sockets

from redis import StrictRedis

from werkzeug.exceptions import default_exceptions, HTTPException

import ConfigParser

from hearts.services.ticket import TicketService
from hearts.services.player import PlayerService, PlayerStateError

from hearts.queue_backend import GameQueueBackend
from hearts.GameBackend import GameBackend

from hearts.game_sockets import GameWebsocketHandler

import hearts.util as u

config = ConfigParser.RawConfigParser()
config.read('config.ini')

redis_host = config.get("Redis", "host")
redis_port = config.getint("Redis", "port")
redis_db = config.getint("Redis", "db")

use_cors = config.getboolean("Main", "use_cors")
main_host = config.get("Main", "host")
main_port = config.getint("Main", "port")

app = Flask(__name__)

if use_cors:
    from flask_cors import CORS
    CORS(app)

sockets = Sockets(app)

redis = StrictRedis(host=redis_host, port=redis_port, db=redis_db)

ticket_svc = TicketService(redis)
player_svc = PlayerService(redis)

game_backend = GameBackend()
queue_backend = GameQueueBackend(game_backend)

ws_handler = GameWebsocketHandler(ticket_svc, queue_backend, game_backend)


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
        password = request.form.get("password")
        if not password:
            password = u.gen_temp_password()

        try:
            player_id = player_svc.create_player(name, password)
        except PlayerStateError:
            player_id = player_svc.get_player_id(name)
            if not player_svc.auth_player(player_id, password):
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

    return jsonify(id=data["id"], name=data["name"])


@sockets.route("/play")
def connect_to_queue(ws):
    ws_handler.handle_ws(ws)


if __name__ == "__main__":
    l = logging.getLogger('cocks')
    l.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    l.addHandler(ch)

    app.debug = True

    server = WSGIServer((main_host, main_port), app, handler_class=WebSocketHandler)
    server.logger = l

    server.serve_forever()
