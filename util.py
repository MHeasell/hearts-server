from random import shuffle


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
    return "player:" + player + ":status"


def is_card(identifier):
    return identifier in DECK


def ticket_key(ticket_id):
    return redis_key("ticket", ticket_id)

def hand_key(game_id, round_number, player):
    return redis_key(
        "game",
        game_id,
        "rounds",
        round_number,
        "players",
        player,
        "hand")


def redis_key(*args):
    args = map(str, args)
    args = map(lambda x: x.replace("\\", "\\\\"), args)
    args = map(lambda x: x.replace(":", "\\:"), args)
    return ":".join(args)