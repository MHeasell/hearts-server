
from redis import StrictRedis, WatchError

from uuid import uuid4

from util import get_status_key, redis_key, STATUS_IN_GAME

from keys import QUEUE_KEY, QUEUE_CHANNEL_KEY, GAME_EVENTS_QUEUE_KEY

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


def create_game(players):
    # we got four players, lets create the game
    game_id = str(uuid4())

    # update the players in redis
    with redis.pipeline() as pipe:

        # TODO: check that the players are still in queuing state
        # before putting them into the game

        # update player state to mark them as in this game
        for player in players:
            status_key = get_status_key(player)
            pipe.set(status_key, STATUS_IN_GAME)
            pipe.set(redis_key("player", player, "current_game"), game_id)

        # add the players to the game's player list
        pipe.rpush(redis_key("game", game_id, "players"), *players)

        # put an init event in the queue
        # so that a dealer will set up this game
        pipe.lpush(GAME_EVENTS_QUEUE_KEY, ",".join(["init", game_id]))

        pipe.execute()


def try_process_queue():
    print "Trying to fetch players..."
    players = try_get_players()

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
