from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

import logging

from flask import Flask, jsonify
from flask_sockets import Sockets

from werkzeug.exceptions import default_exceptions, HTTPException

import ConfigParser

from hearts.services.player import PlayerService

from hearts.queue_backend import GameQueueBackend
from hearts.GameBackend import GameBackend

from hearts.game_sockets import GameWebsocketHandler

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

player_svc = PlayerService()

game_backend = GameBackend()
queue_backend = GameQueueBackend(game_backend)

ws_handler = GameWebsocketHandler(player_svc, queue_backend, game_backend)


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
