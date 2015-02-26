from random import shuffle

from collections import defaultdict

import json


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
        pile_players = map(lambda x: x["player"], pile)
        win_index = find_winning_index(pile_cards)

        for idx, player in enumerate(pile_players):
            if idx == win_index:
                scores[player] += sum_points(pile_cards)
            else:
                scores[player] += 0

    shot_player = None
    for player, score in scores.iteritems():
        if score == 26:
            shot_player = player

    if shot_player is not None:
        for player in scores.iterkeys():
            if player == shot_player:
                scores[player] = 0
            else:
                scores[player] = 26

    return scores


def get_pass_direction(round_number):
    dirs = ["left", "right", "across", "none"];
    idx = (round_number - 1) % 4
    return dirs[idx]


def get_pass_offset(direction):
    if direction == "left":
        return 1
    if direction == "across":
        return 2
    if direction == "right":
        return 3
    if direction == "none":
        return 0


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
