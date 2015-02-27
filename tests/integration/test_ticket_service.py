import unittest

from test_utils import redis_utils

from hearts.services.player import TicketService


class TestTicketService(unittest.TestCase):

    redis_process = None  # this is here to stop IDE complaining

    @classmethod
    def setUpClass(cls):
        cls.redis_process = redis_utils.create_redis_test_process()

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.terminate()

    def setUp(self):
        self.redis = redis_utils.create_redis_test_connection()
        self.svc = TicketService(self.redis)

    def tearDown(self):
        self.redis.flushdb()

    def test_ticket_get_set(self):
        ticket = self.svc.create_ticket_for("Bob")
        name = self.svc.get_player_from_ticket(ticket)

        self.assertEqual("Bob", name)

    def test_ticket_get_set_multiple(self):
        jimbo_ticket = self.svc.create_ticket_for("Jimbo")
        james_ticket = self.svc.create_ticket_for("James")
        bob_ticket = self.svc.create_ticket_for("Bob")

        self.assertEqual("Jimbo", self.svc.get_player_from_ticket(jimbo_ticket))
        self.assertEqual("James", self.svc.get_player_from_ticket(james_ticket))
        self.assertEqual("Bob", self.svc.get_player_from_ticket(bob_ticket))


if __name__ == '__main__':
    unittest.main()
