STATUS_QUEUING = "queuing"
STATUS_IN_GAME = "in_game"


def gen_deck():
    return [s + str(num)
            for s in ["c", "s", "d", "h"]
            for num in range(1, 11) + ["j", "q", "k"]]


DECK = gen_deck()


def get_status_key(player):
    return "player:" + player + ":status"


def is_card(identifier):
    return identifier in DECK


def ticket_key(ticket_id):
    return redis_key("ticket", ticket_id)


def redis_key(*args):
    args = map(lambda x: x.replace("\\", "\\\\"), args)
    args = map(lambda x: x.replace(":", "\\:"), args)
    return ":".join(args)