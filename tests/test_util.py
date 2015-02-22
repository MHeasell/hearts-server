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


if __name__ == '__main__':
    unittest.main()
