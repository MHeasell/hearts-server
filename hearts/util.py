from random import shuffle

import random
import string


def gen_temp_password():
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(16))


DECK = [s + str(num)
        for s in ["c", "s", "d", "h"]
        for num in range(1, 11) + ["j", "q", "k"]]


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


def get_pass_direction(round_number):
    dirs = ["left", "right", "across", "none"]
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


def get_suit(card):
    return card[0]


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
