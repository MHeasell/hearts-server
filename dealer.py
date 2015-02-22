from redis import StrictRedis

from hearts.util import deal_hands
from hearts.services.game import GameService, GameEventQueueService

import json

from collections import defaultdict

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
    scores = defaultdict(int)

    for pile in piles:
        pile = map(json.loads, pile)
        pile_cards = map(lambda x: x["card"], pile)
        win_index = find_winning_index(pile_cards)
        pile_winner = pile[win_index]["player"]
        scores[pile_winner] += sum_points(pile_cards)

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


def find_winning_index(cards):
    parsed_cards = map(parse_card, cards)

    lead_suit = parsed_cards[0][0]

    winner_rank = 0
    winner_index = -1

    for (index, (suit, rank)) in enumerate(parsed_cards):
        if suit != lead_suit:
            continue
        numeric_rank = get_numeric_rank(rank)
        if numeric_rank > winner_rank:
            winner_rank = numeric_rank
            winner_index = index

    return winner_index


def get_numeric_rank(str_rank):
    if str_rank == "j":
        return 11
    if str_rank == "q":
        return 12
    if str_rank == "k":
        return 13
    if str_rank == "1":
        return 14

    return int(str_rank)


def sum_points(cards):
    return sum(map(point_value, cards))


def parse_card(card):
    suit = card[0]
    rank = card[1:]
    return suit, rank


def point_value(card):
    if card == "sq":
        return 13

    suit, rank = parse_card(card)
    if suit == "h":
        return 1

    return 0


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
