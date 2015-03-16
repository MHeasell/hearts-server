import gevent

from hearts.queue_backend import PlayerUnregisteredError

import hearts.websocket_util as wsutil


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
                print "got non-auth message, ignoring."
                wsutil.send_command_fail(ws, command_id)

            print "got auth message"
            ticket = msg.get("ticket")
            if not ticket:
                print "got auth with no ticket, failing."
                wsutil.send_command_fail(ws, command_id)
                continue

            player_id = self.ticket_svc.get_player_id(ticket)
            if player_id is None:
                print "ticket not valid"
                wsutil.send_command_fail(ws, command_id)
                continue

            wsutil.send_command_success(ws, command_id)
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
            result.get()
        except PlayerUnregisteredError:
            print "Player was unregistered, disconnecting."
            return

        listen_greenlet.kill()

        print "game found, handing over to game handler"

        self._handle_game_connection(ws, player_id)

    def _handle_game_connection(self, ws, player_id):
        result = self.game_backend.try_get_game_info(player_id)

        # We know we have a game,
        # so these should definitely exist.
        assert result is not None

        game_id, player_index = result

        game_master = self.game_backend.get_game_master(game_id)

        # this will block until connection close
        game_master.connect(ws, player_id, player_index)
