from random import shuffle

from collections import defaultdict

import json

STATUS_QUEUING = "queuing"
STATUS_IN_GAME = "in_game"


def gen_deck():
    return [s + str(num)
            for s in ["c", "s", "d", "h"]
            for num in range(1, 11) + ["j", "q", "k"]]


DECK = gen_deck()


def deal_hands():
    deck_copy = DECK[:]
    shuffle(deck_copy)

    hands = [
        deck_copy[:13],
        deck_copy[13:26],
        deck_copy[26:39],
        deck_copy[39:52]]

    return hands


def get_status_key(player):
    return redis_key("player", player, "status")


def is_card(identifier):
    return identifier in DECK


def ticket_key(ticket_id):
    return redis_key("ticket", ticket_id)


def redis_key(*args):
    args = map(str, args)
    args = map(lambda x: x.replace("\\", "\\\\"), args)
    args = map(lambda x: x.replace(":", "\\:"), args)
    return ":".join(args)


def find_winning_index(cards):
    parsed_cards = map(_parse_card, cards)

    lead_suit = parsed_cards[0][0]

    winner_rank = 0
    winner_index = -1

    for (index, (suit, rank)) in enumerate(parsed_cards):
        if suit != lead_suit:
            continue
        numeric_rank = _get_numeric_rank(rank)
        if numeric_rank > winner_rank:
            winner_rank = numeric_rank
            winner_index = index

    return winner_index


def sum_points(cards):
    return sum(map(_point_value, cards))


def compute_scores(piles):
    # figure out the scores for this round
    scores = defaultdict(int)

    for pile in piles:
        pile = map(json.loads, pile)
        pile_cards = map(lambda x: x["card"], pile)
        win_index = find_winning_index(pile_cards)
        pile_winner = pile[win_index]["player"]
        scores[pile_winner] += sum_points(pile_cards)

    return scores


def _get_numeric_rank(str_rank):
    if str_rank == "j":
        return 11
    if str_rank == "q":
        return 12
    if str_rank == "k":
        return 13
    if str_rank == "1":
        return 14

    return int(str_rank)


def _parse_card(card):
    suit = card[0]
    rank = card[1:]
    return suit, rank


def _point_value(card):
    if card == "sq":
        return 13

    suit, rank = _parse_card(card)
    if suit == "h":
        return 1

    return 0
