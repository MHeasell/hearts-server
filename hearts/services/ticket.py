from hearts.util import ticket_key

from uuid import uuid4


class TicketService(object):

    def __init__(self, redis):
        self.redis = redis

    def get_player_id(self, ticket):
        val = self.redis.get(ticket_key(ticket))
        if val is None:
            return None
        return int(val)

    def create_ticket_for(self, player_id):
        ticket = str(uuid4())
        self.redis.set(ticket_key(ticket), player_id)
        return ticket
