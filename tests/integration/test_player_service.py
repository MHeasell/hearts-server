import unittest

from test_utils import redis_utils

from hearts.services.player import PlayerService, PlayerStateError


class TestTicketService(unittest.TestCase):

    redis_process = None  # this is here to stop IDE complaining

    @classmethod
    def setUpClass(cls):
        cls.redis_process = redis_utils.RedisTestService()

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.close()

    def setUp(self):
        self.redis = TestTicketService.redis_process.create_connection()
        self.svc = PlayerService(self.redis)

    def tearDown(self):
        self.redis.flushdb()

    def test_create_player_duplicate(self):
        self.svc.create_player("Jimbob")

        self.svc.create_player("Billy")

        try:
            self.svc.create_player("Jimbob")
            self.fail("Expected to throw")
        except PlayerStateError:
            pass  # test passed


if __name__ == '__main__':
    unittest.main()
