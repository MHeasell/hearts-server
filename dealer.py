
from redis import StrictRedis, WatchError

from util import deal_hands, redis_key, hand_key

from keys import GAME_EVENTS_QUEUE_KEY

redis = StrictRedis(host="localhost", port=6379, db=0)


def process_init_event(game_id):
    print "processing init"
    # game has just started,
    # so we should deal for the first round
    hands = deal_hands()

    players_key = redis_key("game", game_id, "players")
    players = redis.lrange(players_key, 0, -1)

    with redis.pipeline() as pipe:
        for (player, hand) in zip(players, hands):
            pipe.sadd(hand_key(game_id, 1, player), *hand)

        # set the current round
        pipe.set(redis_key("game", game_id, "current_round"), 1)

        pipe.execute()


def process_event(event_type, *args):
    if event_type == "init":
        process_init_event(*args)
    else:
        print "Unknown event type: " + event_type

if __name__ == "__main__":
    while True:
        elem = redis.brpop([GAME_EVENTS_QUEUE_KEY])[1]
        params = elem.split(",")
        process_event(*params)
