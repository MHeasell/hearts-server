import gevent

from hearts.queue_backend import PlayerUnregisteredError

import hearts.websocket_util as wsutil

import hearts.util as u

import logging


class GameWebsocketHandler(object):

    def __init__(self, player_svc, queue_backend, game_backend):
        self.player_svc = player_svc
        self.queue_backend = queue_backend
        self.game_backend = game_backend
        self.logger = logging.getLogger(__name__)

    def handle_ws(self, ws):
        self.logger.info("Got connection.")
        player_id = self._receive_auth(ws)
        if player_id is None:
            self.logger.info("Client disconnected during auth.")
            return

        self.logger.info("Authenticated as user %d.", player_id)

        if self.game_backend.is_in_game(player_id):
            self._handle_game_connection(ws, player_id)
        else:
            self._handle_queue_connection(ws, player_id)

    def _receive_auth(self, ws):
        while True:
            msg = wsutil.receive_ws_event(ws)
            if msg is None:
                return None

            command_id = msg["command_id"]

            if msg.get("type") != "auth":
                self.logger.info("Got non-auth message, ignoring.")
                wsutil.send_command_fail(ws, command_id)
                continue

            self.logger.info("Got auth message.")
            username = msg.get("name")
            passwd = msg.get("password")

            if not username:
                self.logger.info("Auth message has incomplete credentials, failing.")
                wsutil.send_command_fail(ws, command_id)
                continue

            if not passwd:
                passwd = u.gen_temp_password()

            if len(username) > 20 or len(passwd) > 50:
                self.logger.info("Credentials too long, rejecting.")
                wsutil.send_command_fail(ws, command_id)
                continue

            player_id = self.player_svc.get_player_id(username)
            if player_id is None:
                self.logger.info("Player with name '%s' does not exist, creating.", username)
                player_id = self.player_svc.create_player(username, passwd)
                self.logger.info("%s created as user %d.", username, player_id)
                wsutil.send_command_success(ws, command_id)
                return player_id

            if self.player_svc.auth_player(player_id, passwd):
                wsutil.send_command_success(ws, command_id)
                return player_id
            else:
                wsutil.send_command_fail(ws, command_id)
                continue

    def _handle_queue_connection(self, ws, player_id):
        # add to queue
        self.logger.info("Checking if player %d is already on the queue.", player_id)
        if self.queue_backend.is_registered(player_id):
            self.logger.info("Player %d is already in queue, disconnecting.", player_id)
            return

        self.logger.info("registering player %d in queue.", player_id)
        result = self.queue_backend.register(player_id)

        # wait for cancel
        def check_cancel():
            while True:
                msg = ws.receive()
                if msg is None or msg == "cancel":
                    self.logger.info("Client cancelled, unregistering player %d.", player_id)
                    self.queue_backend.unregister(player_id)
                    return

        listen_greenlet = gevent.spawn(check_cancel)

        try:
            result.get()
        except PlayerUnregisteredError:
            self.logger.info("Player %d was unregistered, disconnecting and deleting player.", player_id)
            self.player_svc.remove_player(player_id)
            return

        listen_greenlet.kill()

        self.logger.info("Game found for player %d, handing over to game handler.", player_id)

        self._handle_game_connection(ws, player_id)

    def _handle_game_connection(self, ws, player_id):
        player = self.player_svc.get_player(player_id)
        result = self.game_backend.try_get_game_info(player_id)

        # We know we have a game,
        # so these should definitely exist.
        assert result is not None

        game_id, player_index = result

        game_master = self.game_backend.get_game_master(game_id)

        if game_master.is_connected(player_index):
            return

        # this will block until connection close
        game_master.connect(ws, player["name"], player_index)
