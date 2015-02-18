
from redis import StrictRedis, WatchError

from util import deal_hands, redis_key, hand_key

from keys import GAME_EVENTS_QUEUE_KEY

redis = StrictRedis(host="localhost", port=6379, db=0)


def process_init_event(game_id):
    print "processing init for game " + game_id

    # start the first round
    redis.lpush(GAME_EVENTS_QUEUE_KEY, ",".join("start_round", game_id, 1))


def process_start_round_event(game_id, round_id):
    print "processing round " + round_id + " start for game " + game_id

    # deal everyone's hand
    hands = deal_hands()

    players_key = redis_key("game", game_id, "players")
    players = redis.lrange(players_key, 0, -1)

    with redis.pipeline() as pipe:
        # set everyone's hand
        for (player, hand) in zip(players, hands):
            pipe.sadd(hand_key(game_id, round_id, player), *hand)

        # set the current round
        pipe.set(redis_key("game", game_id, "current_round"), round_id)

        pipe.execute()


def process_end_round_event(game_id, round_id):
    print "processing round " + round_id + " end for game " + game_id
    # TODO: do stuff and decide whether to start another round


def process_event(event_type, *args):
    if event_type == "init":
        process_init_event(*args)
    elif event_type == "start_round":
        process_start_round_event(*args)
    elif event_type == "end_round":
        process_end_round_event(*args)
    else:
        print "Unknown event type: " + event_type

if __name__ == "__main__":
    while True:
        elem = redis.brpop([GAME_EVENTS_QUEUE_KEY])[1]
        params = elem.split(",")
        process_event(*params)
