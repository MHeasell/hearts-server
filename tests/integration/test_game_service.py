import unittest

from test_utils import redis_utils

from hearts.services.game import GameService, GameNotFoundError


class TestGameService(unittest.TestCase):

    redis_process = None  # this is here to stop IDE complaining

    @classmethod
    def setUpClass(cls):
        cls.redis_process = redis_utils.RedisTestService()

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.close()

    def setUp(self):
        self.redis = TestGameService.redis_process.create_connection()
        self.svc = GameService(self.redis)

    def tearDown(self):
        self.redis.flushdb()

    def test_create_game(self):
        game_id = self.svc.create_game([1000, 1001, 1002, 1003])

        data = self.svc.get_game(game_id)

        expected = {
            "id": game_id,
            "current_round": 0,
            "players": [
                {"id": 1000, "score": 0},
                {"id": 1001, "score": 0},
                {"id": 1002, "score": 0},
                {"id": 1003, "score": 0},
            ]
        }

        self.assertEqual(expected, data)

    def test_create_game_multiple(self):
        game_id_1 = self.svc.create_game([2, 4, 6, 8])
        game_id_2 = self.svc.create_game([3, 5, 7, 9])

        self.assertNotEqual(game_id_1, game_id_2)

        game_1_data = self.svc.get_game(game_id_1)
        game_2_data = self.svc.get_game(game_id_2)

        self.assertEqual(game_id_1, game_1_data["id"])
        self.assertEqual(game_id_2, game_2_data["id"])

    def test_set_current_round(self):
        game_id = self.svc.create_game([1, 2, 3, 4])
        self.svc.set_current_round(game_id, 2)
        game = self.svc.get_game(game_id)

        self.assertEqual(2, game["current_round"])

    def test_set_current_round_not_existing(self):
        try:
            self.svc.set_current_round(1234, 2)
            self.fail()
        except GameNotFoundError:
            pass  # test succeeded

    def test_add_to_scores(self):
        game_id = self.svc.create_game([2, 4, 6, 8])
        scores = {
            2: 5,
            4: 10,
            6: 3,
            8: 8
        }

        new_scores = self.svc.add_to_scores(game_id, scores)

        # scores start at zero
        # so they should be the same as what we put in now.
        self.assertEqual(scores, new_scores)

    def test_add_to_scores_multiple(self):
        game_id = self.svc.create_game([2, 4, 6, 8])
        scores = {
            2: 5,
            4: 10,
            6: 3,
            8: 8
        }

        self.svc.add_to_scores(game_id, scores)
        final_scores = self.svc.add_to_scores(game_id, scores)

        expected = {
            2: 10,
            4: 20,
            6: 6,
            8: 16
        }

        # scores start at zero
        # so they should be the same as what we put in now.
        self.assertEqual(expected, final_scores)
