from redis import StrictRedis

from hearts.keys import QUEUE_CHANNEL_KEY
from hearts.services.game import GameService, GameEventQueueService
from hearts.services.player import PlayerStateError
from hearts.services.queue import QueueService

redis = StrictRedis(host="localhost", port=6379, db=0)

game_svc = GameService(redis)

game_evt_queue_svc = GameEventQueueService(redis)

queue_svc = QueueService(redis)


def create_game(players):
    # set up the game
    try:
        game_id = game_svc.create_game(players)
    except PlayerStateError:
        # Some player must have left the queue
        # or gone away.
        # Try to place each player back in queue.
        for player in players:
            try:
                queue_svc.readd_player(player)
            except PlayerStateError:
                pass

        return

    # put an init event in the queue
    # so that a dealer will set up this game
    game_evt_queue_svc.raise_init_event(game_id)


def try_process_queue():
    print "Trying to fetch players..."
    players = queue_svc.try_get_players(4)

    if players is None:
        print "Not enough players found."
        return False

    print "Four players found, creating game."
    create_game(players)
    return True


def consume_queue():
    while try_process_queue():
        pass


if __name__ == "__main__":
    # set up subscription
    print "Setting up subscription..."
    p = redis.pubsub(ignore_subscribe_messages=True)
    p.subscribe(QUEUE_CHANNEL_KEY)

    # consume whatever is already in the queue
    print "Performing initial queue check..."
    consume_queue()

    # whenever the queue changes, try to process it
    print "Waiting for messages..."

    try:
        for message in p.listen():
            print "Got message."
            consume_queue()
    except KeyboardInterrupt:
        print "Received interrupt signal, terminating."
    finally:
        p.close()
