from hearts.util import ticket_key

from uuid import uuid4


class TicketService(object):

    def __init__(self, redis):
        self.redis = redis

    def get_value(self, ticket):
        return self.redis.get(ticket_key(ticket))

    def create_ticket_for(self, player):
        ticket = str(uuid4())
        self.redis.set(ticket_key(ticket), player)
        return ticket
