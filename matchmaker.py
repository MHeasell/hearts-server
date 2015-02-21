
from uuid import uuid4

from redis import StrictRedis, WatchError

from keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

from game import GameService, GameEventQueueService

from player import PlayerService

from queue import QueueService

redis = StrictRedis(host="localhost", port=6379, db=0)


def create_game(players):
    game_id = str(uuid4())

    game_svc = GameService(redis, game_id)

    player_svc = PlayerService(redis)

    game_queue_svc = GameEventQueueService(redis)

    # set up the game
    game_svc.create_game(players)

    # change the players' statuses to be in-game
    player_svc.set_as_in_game(game_id, *players)

    # put an init event in the queue
    # so that a dealer will set up this game
    game_queue_svc.raise_init_event(game_id)


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
    for message in p.listen():
        print "Got message."
        consume_queue()
