from redis import StrictRedis

from hearts.util import deal_hands
from hearts.keys import GAME_EVENTS_QUEUE_KEY
from hearts.game import GameService

redis = StrictRedis(host="localhost", port=6379, db=0)


def process_init_event(game_id):
    print "processing init for game " + game_id

    # start the first round
    redis.lpush(GAME_EVENTS_QUEUE_KEY, ",".join(["start_round", game_id, "1"]))


def process_start_round_event(game_id, round_id):
    print "processing round " + round_id + " start for game " + game_id

    game_svc = GameService(redis)
    round_svc = game_svc.get_round_service(game_id, round_id)

    players = game_svc.get_players(game_id)

    # deal everyone's hand
    hands = deal_hands()
    round_svc.set_hands(players, hands)

    # set the current round
    game_svc.set_current_round(game_id, round_id)


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
