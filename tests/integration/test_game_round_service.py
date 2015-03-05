import unittest

from test_utils import redis_utils

from hearts.services.game import GameService, RoundNotFoundError, GameStateError, AccessDeniedError

example_hands = {
    1001: ['h5', 's7', 'c2', 'h1', 'd2', 'h8', 'd3', 's2', 'd9', 'c5', 'd8', 'dq', 'c4'],
    1002: ['c10', 'h6', 'c3', 'h10', 'hk', 'd7', 'dk', 'h4', 'sj', 'hq', 'hj', 's5', 'd5'],
    1003: ['s6', 's10', 'd1', 'sk', 's4', 'h7', 'd10', 'sq', 'c9', 'cq', 'd6', 'h2', 'cj'],
    1004: ['d4', 'c8', 'h9', 'ck', 'h3', 'c6', 'dj', 's9', 's1', 'c1', 's3', 'c7', 's8']
}


class TestGameRoundService(unittest.TestCase):

    redis_process = None  # this is here to stop IDE complaining

    @classmethod
    def setUpClass(cls):
        cls.redis_process = redis_utils.RedisTestService()

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.close()

    def setUp(self):
        self.redis = TestGameRoundService.redis_process.create_connection()
        self.game_svc = GameService(self.redis)
        self.game_id = self.game_svc.create_game([1001, 1002, 1003, 1004])
        self.round_svc = self.game_svc.get_round_service(self.game_id)

    def tearDown(self):
        self.redis.flushdb()

    def test_get_hand_nonexistent_round(self):
        try:
            self.round_svc.get_hand(1234, 1000)
            self.fail()
        except RoundNotFoundError:
            pass  # test succeeded

    def test_create_round(self):
        hands = {
            1001: ["c2"],
            1002: ["d2"],
            1003: ["s2"],
            1004: ["h2"],
        }

        round_id = self.round_svc.create_round(hands)

        data = self.round_svc.get_round(round_id)

        expected = {
            "id": round_id,
            "state": "passing",
            "current_pile": 0
        }

        self.assertEqual(expected, data)

    def test_create_round_hands(self):
        round_id = self.round_svc.create_round(example_hands)

        hand_1 = self.round_svc.get_hand(round_id, 1001)
        hand_2 = self.round_svc.get_hand(round_id, 1002)
        hand_3 = self.round_svc.get_hand(round_id, 1003)
        hand_4 = self.round_svc.get_hand(round_id, 1004)

        self.assertEqual(set(example_hands[1001]), hand_1)
        self.assertEqual(set(example_hands[1002]), hand_2)
        self.assertEqual(set(example_hands[1003]), hand_3)
        self.assertEqual(set(example_hands[1004]), hand_4)

    def test_pass_cards(self):
        round_id = self.round_svc.create_round(example_hands)

        self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "c2"])
        self.round_svc.pass_cards(round_id, 1002, 1003, ["c10", "h6", "c3"])
        self.round_svc.pass_cards(round_id, 1003, 1004, ["s6", "s10", "d1"])
        self.round_svc.pass_cards(round_id, 1004, 1001, ["d4", "c8", "h9"])

        data = self.round_svc.get_passed_cards(round_id, 1002)

        self.assertEqual({"h5", "s7", "c2"}, data)

    def test_pass_cards_wrong_player(self):
        round_id = self.round_svc.create_round(example_hands)

        try:
            self.round_svc.pass_cards(round_id, 1001, 1003, ["h5", "s7", "c2"])
            self.fail()
        except AccessDeniedError:
            pass  # test succeeded

    def test_access_passed_cards_before_play(self):
        """
        Shouldn't be able to get a player's received cards
        before *everyone* has passed cards.
        """
        round_id = self.round_svc.create_round(example_hands)

        try:
            self.round_svc.get_passed_cards(round_id, 1002)
            self.fail()
        except AccessDeniedError:
            pass  # test succeeded

    def test_access_passed_cards_before_play_after_pass(self):
        """
        Shouldn't be able to get a player's received cards
        before *everyone* has passed cards.
        """
        round_id = self.round_svc.create_round(example_hands)

        self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "c2"])
        self.round_svc.pass_cards(round_id, 1004, 1001, ["d4", "c8", "h9"])

        try:
            self.round_svc.get_passed_cards(round_id, 1001)
            self.fail()
        except AccessDeniedError:
            pass  # test succeeded

    def test_pass_cards_twice(self):
        round_id = self.round_svc.create_round(example_hands)

        self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "c2"])

        try:
            self.round_svc.pass_cards(round_id, 1001, 1002, ["h1", "d2", "h8"])
            self.fail()
        except GameStateError:
            pass  # test succeeded

    def test_pass_cards_not_in_hand(self):
        round_id = self.round_svc.create_round(example_hands)

        try:
            self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "s6"])
            self.fail()
        except GameStateError:
            pass  # test succeeded

    def test_play_card_before_start(self):
        round_id = self.round_svc.create_round(example_hands)

        try:
            self.round_svc.play_card(round_id, 1, 1001, "c2")
            self.fail()
        except GameStateError:
            pass  # test succeeded

    def test_play_card(self):
        round_id = self.round_svc.create_round(example_hands)

        self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "c2"])
        self.round_svc.pass_cards(round_id, 1002, 1003, ["c10", "h6", "c3"])
        self.round_svc.pass_cards(round_id, 1003, 1004, ["s6", "s10", "d1"])
        self.round_svc.pass_cards(round_id, 1004, 1001, ["d4", "c8", "h9"])

        self.round_svc.play_card(round_id, 1, 1002, "c2")

        pile = self.round_svc.get_pile(round_id, 1)
        expected = [{"player": 1002, "card": "c2"}]
        self.assertEqual(expected, pile)

        card = self.round_svc.get_pile_card(round_id, 1, 1)
        expected_card = {"player": 1002, "card": "c2"}
        self.assertEqual(expected_card, card)

        all_piles = self.round_svc.get_all_piles(round_id)
        expected_all_piles = [[{"player": 1002, "card": "c2"}]]
        self.assertEqual(expected_all_piles, all_piles)

    def test_play_card_wrong_pile(self):
        round_id = self.round_svc.create_round(example_hands)

        self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "c2"])
        self.round_svc.pass_cards(round_id, 1002, 1003, ["c10", "h6", "c3"])
        self.round_svc.pass_cards(round_id, 1003, 1004, ["s6", "s10", "d1"])
        self.round_svc.pass_cards(round_id, 1004, 1001, ["d4", "c8", "h9"])

        try:
            self.round_svc.play_card(round_id, 2, 1002, "c2")
            self.fail()
        except GameStateError:
            pass  # test succeeded

    def test_play_card_not_our_turn(self):
        round_id = self.round_svc.create_round(example_hands)

        self.round_svc.pass_cards(round_id, 1001, 1002, ["h5", "s7", "c2"])
        self.round_svc.pass_cards(round_id, 1002, 1003, ["c10", "h6", "c3"])
        self.round_svc.pass_cards(round_id, 1003, 1004, ["s6", "s10", "d1"])
        self.round_svc.pass_cards(round_id, 1004, 1001, ["d4", "c8", "h9"])

        try:
            self.round_svc.play_card(round_id, 1, 1001, "c5")
            self.fail()
        except GameStateError:
            pass  # test succeeded