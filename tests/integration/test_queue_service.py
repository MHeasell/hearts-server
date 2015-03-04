import unittest

from test_utils import redis_utils

from hearts.services.queue import QueueService


class TestQueueService(unittest.TestCase):

    redis_process = None  # this is here to stop IDE complaining

    @classmethod
    def setUpClass(cls):
        cls.redis_process = redis_utils.RedisTestService()

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.close()

    def setUp(self):
        self.redis = TestQueueService.redis_process.create_connection()
        self.svc = QueueService(self.redis)

    def tearDown(self):
        self.redis.flushdb()

    def test_pop_empty(self):
        result = self.svc.try_pop_players(1)
        self.assertIsNone(result)

    def test_pop(self):
        self.svc.add_player(1000)
        result = self.svc.try_pop_players(1)
        self.assertEqual(1, len(result))
        self.assertEqual(1000, result[0])

    def test_pop_too_few(self):
        self.svc.add_player(1000)
        result = self.svc.try_pop_players(2)
        self.assertIsNone(result)

    def test_pop_multiple(self):
        self.svc.add_player(1000)
        self.svc.add_player(4200)
        self.svc.add_player(3000)

        result = self.svc.try_pop_players(2)
        result_2 = self.svc.try_pop_players(2)
        result_3 = self.svc.try_pop_players(1)

        self.assertEqual(2, len(result))
        self.assertEqual(1000, result[0])
        self.assertEqual(4200, result[1])

        self.assertIsNone(result_2)

        self.assertEqual(1, len(result_3))
        self.assertEqual(3000, result_3[0])


if __name__ == '__main__':
    unittest.main()
