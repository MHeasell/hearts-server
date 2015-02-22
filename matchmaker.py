from redis import StrictRedis

from hearts.keys import QUEUE_CHANNEL_KEY
from hearts.services.game import GameService, GameEventQueueService
from hearts.services.player import PlayerService, PlayerStateError
from hearts.services.queue import QueueService

redis = StrictRedis(host="localhost", port=6379, db=0)


def create_game(players):
    game_svc = GameService(redis)

    player_svc = PlayerService(redis)

    game_queue_svc = GameEventQueueService(redis)

    # set up the game
    try:
        game_id = game_svc.create_game(players)

        # put an init event in the queue
        # so that a dealer will set up this game
        game_queue_svc.raise_init_event(game_id)

    except PlayerStateError:
        # TODO: stuff remaining player back into the queue
        # instead of just dumping them
        pass


def try_process_queue():

    svc = QueueService(redis)

    print "Trying to fetch players..."
    players = svc.try_get_players(4)

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
