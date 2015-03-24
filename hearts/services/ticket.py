from uuid import uuid4


class TicketService(object):

    def __init__(self):
        self._tickets = {}

    def get_player_id(self, ticket):
        return self._tickets.get(ticket)

    def create_ticket_for(self, player_id):
        ticket = str(uuid4())
        self._tickets[ticket] = player_id
        return ticket
