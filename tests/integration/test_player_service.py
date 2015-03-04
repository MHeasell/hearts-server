import unittest

from test_utils import redis_utils

from hearts.services.player import PlayerService, PlayerStateError


class TestPlayerService(unittest.TestCase):

    redis_process = None  # this is here to stop IDE complaining

    @classmethod
    def setUpClass(cls):
        cls.redis_process = redis_utils.RedisTestService()

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.close()

    def setUp(self):
        self.redis = TestPlayerService.redis_process.create_connection()
        self.svc = PlayerService(self.redis)

    def tearDown(self):
        self.redis.flushdb()

    def test_create_player(self):
        player_id = self.svc.create_player("Joe")
        player = self.svc.get_player(player_id)

        self.assertEqual(player_id, player["id"])
        self.assertEqual("Joe", player["name"])
        self.assertEqual("idle", player["status"])

    def test_create_player_duplicate(self):
        self.svc.create_player("Jimbob")

        self.svc.create_player("Billy")

        try:
            self.svc.create_player("Jimbob")
            self.fail("Expected to throw")
        except PlayerStateError:
            pass  # test passed

    def test_get_id(self):
        player_id = self.svc.create_player("Steve")
        fetched_id = self.svc.get_player_id("Steve")

        self.assertEqual(player_id, fetched_id)

    def test_get_by_name(self):
        player_id = self.svc.create_player("Jimmy")
        player = self.svc.get_player_by_name("Jimmy")

        self.assertEqual(player_id, player["id"])
        self.assertEqual("Jimmy", player["name"])
        self.assertEqual("idle", player["status"])


if __name__ == '__main__':
    unittest.main()
