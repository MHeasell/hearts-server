import unittest

from hearts.model.preround import HeartsPreRound
import hearts.util as u
import hearts.model.exceptions as m

example_hands = [
    ['h5', 's7', 'c2', 'h1', 'd2', 'h8', 'd3', 's2', 'd9', 'c5', 'd8', 'dq', 'c4'],
    ['c10', 'h6', 'c3', 'h10', 'hk', 'd7', 'dk', 'h4', 'sj', 'hq', 'hj', 's5', 'd5'],
    ['s6', 's10', 'd1', 'sk', 's4', 'h7', 'd10', 'sq', 'c9', 'cq', 'd6', 'h2', 'cj'],
    ['d4', 'c8', 'h9', 'ck', 'h3', 'c6', 'dj', 's9', 's1', 'c1', 's3', 'c7', 's8']
]


class TestHeartsPreRound(unittest.TestCase):

    def test_init(self):
        round = HeartsPreRound(example_hands)
        for i in range(4):
            self.assertEqual(example_hands[i], round.get_hand(i))

    def test_start_round_hand_modification(self):
        """
        The object should copy hands it takes in.
        """
        hands = u.deal_hands()
        round = HeartsPreRound(hands)

        # try to modify the hand we passed in
        hands[0].pop()

        # this should not have changed the given hand
        self.assertNotEqual(len(hands[0]), len(round.get_hand(0)))

    def test_start_round_get_hand_modification(self):
        """
        The object should copy hands it emits via get_hand
        """
        hands = u.deal_hands()
        round = HeartsPreRound(hands)

        hand = round.get_hand(0)
        hand.pop()

        # this should not have changed the given hand
        self.assertNotEqual(len(hand), len(round.get_hand(0)))

    def test_pass_cards_not_in_hand(self):
        """
        We should not be allowed to pass cards not in our hand.
        """
        round = HeartsPreRound(example_hands)

        cards_to_pass = ["h5", "h7", "sk"]  # sk is not in our hand

        try:
            round.pass_cards(0, cards_to_pass)
            self.fail()
        except m.CardsNotInHandError:
            pass  # test succeeded


    def test_pass_too_few_cards(self):
        """
        We should not be allowed to pass fewer than 3 cards.
        """
        round = HeartsPreRound(example_hands)

        cards_to_pass = ["h5", "s7"]

        try:
            round.pass_cards(0, cards_to_pass)
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_pass_too_many_cards(self):
        """
        We should not be allowed to pass fewer than 3 cards.
        """
        round = HeartsPreRound(example_hands)

        cards_to_pass = ["h5", "s7", "c2", "h1"]

        try:
            round.pass_cards(0, cards_to_pass)
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_pass_cards_twice(self):
        """
        We should not be allowed to pass cards more than once.
        """
        round = HeartsPreRound(example_hands)

        cards_to_pass = ["h5", "s7", "c2"]
        round.pass_cards(0, cards_to_pass)

        try:
            round.pass_cards(0, cards_to_pass)
            self.fail()
        except m.CardsAlreadyPassedError:
            pass  # test succeeded

    def test_finish_passing_not_all_passed(self):
        """
        We should not be able to finish passing
        when not all players have passed.
        """
        round = HeartsPreRound(example_hands)

        # last player does not pass
        for i in range(3):
            round.pass_cards(i, example_hands[i][:3])

        try:
            round.finish_passing()
            self.fail()
        except m.PlayersYetToPassError:
            pass  # test succeeded

    def test_finish_passing_update_hands(self):
        """
        When passing is finished,
        passed cards should be transferred to players' hands.
        """
        round = HeartsPreRound(example_hands)

        for i in range(4):
            round.pass_cards(i, example_hands[i][:3])

        round.finish_passing()

        for card in example_hands[0][:3]:
            self.assertNotIn(card, round.get_hand(0))
            self.assertIn(card, round.get_hand(1))

        for card in example_hands[1][:3]:
            self.assertNotIn(card, round.get_hand(1))
            self.assertIn(card, round.get_hand(2))

        for card in example_hands[2][:3]:
            self.assertNotIn(card, round.get_hand(2))
            self.assertIn(card, round.get_hand(3))

        for card in example_hands[3][:3]:
            self.assertNotIn(card, round.get_hand(3))
            self.assertIn(card, round.get_hand(0))

    def test_finish_passing_update_hands_across(self):
        """
        When the pass direction is across,
        when passing is finished,
        passed cards should be transferred to opposite players' hands.
        """
        round = HeartsPreRound(example_hands, "across")

        for i in range(4):
            round.pass_cards(i, example_hands[i][:3])

        round.finish_passing()

        for card in example_hands[0][:3]:
            self.assertNotIn(card, round.get_hand(0))
            self.assertIn(card, round.get_hand(2))

        for card in example_hands[1][:3]:
            self.assertNotIn(card, round.get_hand(1))
            self.assertIn(card, round.get_hand(3))

        for card in example_hands[2][:3]:
            self.assertNotIn(card, round.get_hand(2))
            self.assertIn(card, round.get_hand(0))

        for card in example_hands[3][:3]:
            self.assertNotIn(card, round.get_hand(3))
            self.assertIn(card, round.get_hand(1))

    def test_finish_passing_update_hands_right(self):
        """
        When the pass direction is right,
        when passing is finished,
        passed cards should be transferred to previous players' hands.
        """
        round = HeartsPreRound(example_hands, "right")

        for i in range(4):
            round.pass_cards(i, example_hands[i][:3])

        round.finish_passing()

        for card in example_hands[0][:3]:
            self.assertNotIn(card, round.get_hand(0))
            self.assertIn(card, round.get_hand(3))

        for card in example_hands[1][:3]:
            self.assertNotIn(card, round.get_hand(1))
            self.assertIn(card, round.get_hand(0))

        for card in example_hands[2][:3]:
            self.assertNotIn(card, round.get_hand(2))
            self.assertIn(card, round.get_hand(1))

        for card in example_hands[3][:3]:
            self.assertNotIn(card, round.get_hand(3))
            self.assertIn(card, round.get_hand(2))

    def test_have_all_passed_init(self):
        """
        When the class is initialized,
        not all players should have passed.
        """
        round = HeartsPreRound(example_hands)

        self.assertFalse(round.have_all_passed())

    def test_have_all_passed_after_passing(self):
        """
        When all 4 players have passed, have_all_passed
        should return true
        """

        round = HeartsPreRound(example_hands)

        for i in range(4):
            round.pass_cards(i, example_hands[i][:3])

        self.assertTrue(round.have_all_passed())

    def test_have_all_passed_after_almost_passing(self):
        """
        When all 4 players have passed, have_all_passed
        should return true
        """

        round = HeartsPreRound(example_hands)

        # only 3 players pass
        for i in range(3):
            round.pass_cards(i, example_hands[i][:3])

        self.assertFalse(round.have_all_passed())

if __name__ == '__main__':
    unittest.main()
