
from uuid import uuid4

from redis import StrictRedis, WatchError

from keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

from game import create_game

redis = StrictRedis(host="localhost", port=6379, db=0)


def try_get_players():
    with redis.pipeline() as pipe:
        while True:
            try:
                pipe.watch(QUEUE_KEY)

                queue_length = pipe.llen(QUEUE_KEY)
                if queue_length < 4:
                    return None

                pipe.multi()
                pipe.lrange(QUEUE_KEY, -4, -1)
                pipe.ltrim(QUEUE_KEY, 0, -5)
                result = pipe.execute()

                return result[0]

            except WatchError:
                continue


def try_process_queue():
    print "Trying to fetch players..."
    players = try_get_players()

    if players is None:
        print "Not enough players found."
        return False

    print "Four players found, creating game."
    game_id = str(uuid4())
    create_game(redis, game_id, players)
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
