from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

import logging
import time

from flask import Flask, jsonify
from flask_sockets import Sockets

from werkzeug.exceptions import default_exceptions, HTTPException

import ConfigParser

from hearts.services.player import PlayerService

from hearts.queue_backend import GameQueueBackend
from hearts.game_backend import GameBackend

from hearts.game_sockets import GameWebsocketHandler

config = ConfigParser.RawConfigParser()
config.read('config.ini')

use_cors = config.getboolean("Main", "use_cors")
main_host = config.get("Main", "host")
main_port = config.getint("Main", "port")
logfile = config.get("Main", "logfile")

app = Flask(__name__)

if use_cors:
    from flask_cors import CORS
    CORS(app)

sockets = Sockets(app)

player_svc = PlayerService()

game_backend = GameBackend(player_svc)
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
    try:
        ws_handler.handle_ws(ws)
    except Exception:
        logging.error("Unhandled exception.", exc_info=True)


if __name__ == "__main__":

    formatter = logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s', '%Y-%m-%d %H:%M:%S %Z')
    formatter.converter = time.localtime

    if logfile == "-":
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(logfile)

    handler.setFormatter(formatter)

    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)

    app.debug = True

    server = WSGIServer((main_host, main_port), app, handler_class=WebSocketHandler)

    logging.info("Server started.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Interrupt recieved, server shutting down.")
