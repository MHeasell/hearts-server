import unittest

import hearts.util as u


class TestSumPoints(unittest.TestCase):
    def test_empty(self):
        self._check_sum([], 0)

    def test_simple(self):
        self._check_sum(["c3", "s2", "d4"], 0)

    def test_hearts(self):
        self._check_sum(["h4"], 1)

    def test_hearts_multiple(self):
        self._check_sum(["h4", "h6", "d5", "c7", "h10"], 3)

    def test_queen_spades(self):
        self._check_sum(["sq"], 13)

    def test_queen_spades_multiple(self):
        self._check_sum(["s4", "h1", "c3", "hq", "sq", "d1"], 15)

    def _check_sum(self, data, expected):
        self.assertEqual(expected, u.sum_points(data))


class TestFindWinningIndex(unittest.TestCase):
    def test_simple(self):
        self._check_idx(["c2", "c3", "c4", "c5"], 3)

    def test_shuffled(self):
        self._check_idx(["c7", "c5", "c8", "c4"], 2)

    def test_face_cards(self):
        self._check_idx(["c5", "ck", "cj", "cq"], 1)

    def test_aces(self):
        self._check_idx(["c3", "c1", "c6", "c7"], 1)

    def test_mixed_suit(self):
        self._check_idx(["h2", "c10", "h6", "h4"], 2)

    def _check_idx(self, data, expected):
        self.assertEqual(expected, u.find_winning_index(data))


class TestDealHands(unittest.TestCase):
    def test_no_duplicates(self):
        seen_cards = set()

        hands = u.deal_hands()

        # check that each card appears only once
        for hand in hands:
            for card in hand:
                if card in seen_cards:
                    self.fail()
                seen_cards.add(card)

    def test_correct_length(self):
        hands = u.deal_hands()
        self.assertEqual(4, len(hands))

        for hand in hands:
            self.assertEqual(13, len(hand))


class TestRedisKey(unittest.TestCase):
    def test_empty(self):
        self._check_key([], "")

    def test_simple(self):
        self._check_key(["simple"], "simple")

    def test_multiple(self):
        self._check_key(["foo", "bar"], "foo:bar")

    def test_three(self):
        self._check_key(["foo", "bar", "baz"], "foo:bar:baz")

    def test_non_str(self):
        self._check_key(["foo", 1, 5], "foo:1:5")

    def test_escape(self):
        self._check_key(["foo:bar"], r"foo\:bar")

    def test_escape_slash(self):
        self._check_key([r"foo\bar"], r"foo\\bar")

    def test_escape_slash_colon(self):
        self._check_key([r"foo\:bar"], r"foo\\\:bar")

    def _check_key(self, data, expected):
        self.assertEqual(expected, u.redis_key(*data))


class TestComputeScores(unittest.TestCase):
    def test_simple(self):

        data = [
            [
                '{ "card":"c2", "player":"Alice"}',
                '{ "card":"c3", "player":"Bob"}',
                '{ "card":"c4", "player":"Charlie"}',
                '{ "card":"c5", "player":"David"}',
            ]
        ]

        scores = u.compute_scores(data)

        self.assertEqual(0, scores["Alice"])
        self.assertEqual(0, scores["Bob"])
        self.assertEqual(0, scores["Charlie"])
        self.assertEqual(0, scores["David"])

    def test_multiple(self):

        data = [
            [
                '{ "card":"c2", "player":"Alice"}',
                '{ "card":"c3", "player":"Bob"}',
                '{ "card":"c4", "player":"Charlie"}',
                '{ "card":"c5", "player":"David"}',
            ],
            [
                '{ "card":"c6", "player":"David"}',
                '{ "card":"c7", "player":"Alice"}',
                '{ "card":"c8", "player":"Bob"}',
                '{ "card":"h2", "player":"Charlie"}',
            ],
            [
                '{ "card":"h3", "player":"Bob"}',
                '{ "card":"s5", "player":"Charlie"}',
                '{ "card":"h10", "player":"David"}',
                '{ "card":"sq", "player":"Alice"}',
            ]
        ]

        scores = u.compute_scores(data)

        self.assertEqual(0, scores["Alice"])
        self.assertEqual(1, scores["Bob"])
        self.assertEqual(0, scores["Charlie"])
        self.assertEqual(15, scores["David"])

    def test_shoot_moon(self):
        data = [
            [
                '{ "card":"h5", "player":"Alice"}',
                '{ "card":"h4", "player":"Bob"}',
                '{ "card":"h3", "player":"Charlie"}',
                '{ "card":"h2", "player":"David"}',
            ],
            [
                '{ "card":"h9", "player":"Alice"}',
                '{ "card":"h8", "player":"Bob"}',
                '{ "card":"h7", "player":"Charlie"}',
                '{ "card":"h6", "player":"David"}',
            ],
            [
                '{ "card":"hk", "player":"Alice"}',
                '{ "card":"hq", "player":"Bob"}',
                '{ "card":"hj", "player":"Charlie"}',
                '{ "card":"h10", "player":"David"}',
            ],
            [
                '{ "card":"h1", "player":"Alice"}',
                '{ "card":"sq", "player":"Bob"}',
                '{ "card":"s2", "player":"Charlie"}',
                '{ "card":"s3", "player":"David"}',
            ],
        ]

        scores = u.compute_scores(data)

        self.assertEqual(0, scores["Alice"])
        self.assertEqual(26, scores["Bob"])
        self.assertEqual(26, scores["Charlie"])
        self.assertEqual(26, scores["David"])


class TestGetPassDirection(unittest.TestCase):
    def test_simple(self):
        self.assertEqual("left", u.get_pass_direction(1))
        self.assertEqual("right", u.get_pass_direction(2))
        self.assertEqual("across", u.get_pass_direction(3))
        self.assertEqual("none", u.get_pass_direction(4))

        self.assertEqual("left", u.get_pass_direction(5))
        self.assertEqual("right", u.get_pass_direction(6))
        self.assertEqual("across", u.get_pass_direction(7))
        self.assertEqual("none", u.get_pass_direction(8))


if __name__ == '__main__':
    unittest.main()
