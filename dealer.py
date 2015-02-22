from redis import StrictRedis

from hearts.util import deal_hands, compute_scores
from hearts.services.game import GameService, GameEventQueueService

redis = StrictRedis(host="localhost", port=6379, db=0)

queue_svc = GameEventQueueService(redis)


def process_init_event(game_id):
    print "processing init for game " + game_id

    # start the first round
    queue_svc.raise_start_round_event(game_id, 1)


def process_start_round_event(game_id, round_number):
    print "processing round " + str(round_number) + " start for game " + game_id

    game_svc = GameService(redis)
    round_svc = game_svc.get_round_service(game_id, round_number)

    players = game_svc.get_players(game_id)

    # deal everyone's hand
    hands = deal_hands()
    round_svc.set_hands(players, hands)

    # set the current round
    game_svc.set_current_round(game_id, round_number)


def process_end_round_event(game_id, round_number):
    print "processing round " + str(round_number) + " end for game " + game_id

    game_svc = GameService(redis)
    round_svc = game_svc.get_round_service(game_id, round_number)

    piles = round_svc.get_all_piles()

    # figure out the scores for this round
    scores = compute_scores(piles)

    new_scores_dict = game_svc.add_to_scores(game_id, scores)

    game_over = False

    for score in new_scores_dict.itervalues():
        if score >= 100:
            game_over = True
            break

    if game_over:
        queue_svc.raise_end_game_event(game_id)
    else:
        queue_svc.raise_start_round_event(game_id, round_number + 1)


def process_event(event_type, *args):
    if event_type == "init":
        process_init_event(args[0])
    elif event_type == "start_round":
        process_start_round_event(args[0], int(args[1]))
    elif event_type == "end_round":
        process_end_round_event(args[0], int(args[1]))
    else:
        print "Unknown event type: " + event_type

if __name__ == "__main__":
    try:
        while True:
            params = queue_svc.blocking_pop_event()
            process_event(*params)
    except KeyboardInterrupt:
        print "Received interrupt signal, terminating."
