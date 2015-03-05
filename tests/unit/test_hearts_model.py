import unittest

from hearts.game_model import HeartsGame, HeartsRound
import hearts.game_model as m

import hearts.util as u


example_hands = [
    ['h5', 's7', 'c2', 'h1', 'd2', 'h8', 'd3', 's2', 'd9', 'c5', 'd8', 'dq', 'c4'],
    ['c10', 'h6', 'c3', 'h10', 'hk', 'd7', 'dk', 'h4', 'sj', 'hq', 'hj', 's5', 'd5'],
    ['s6', 's10', 'd1', 'sk', 's4', 'h7', 'd10', 'sq', 'c9', 'cq', 'd6', 'h2', 'cj'],
    ['d4', 'c8', 'h9', 'ck', 'h3', 'c6', 'dj', 's9', 's1', 'c1', 's3', 'c7', 's8']
]


class TestHeartsModel(unittest.TestCase):

    def test_init_scores(self):
        """
        When the game is first initialized,
        the score for each player should be zero.
        """
        game = HeartsGame()

        for i in range(4):
            self.assertEqual(0, game.get_score(i))


class TestHeartsRound(unittest.TestCase):

    def test_init(self):
        round = HeartsRound(example_hands)
        for i in range(4):
            self.assertEqual(example_hands[i], round.get_hand(i))

    def test_init_get_current_player(self):
        """
        When the round is first initialized,
        get_current_player should fail
        as play has started yet.
        """
        round = HeartsRound(example_hands)

        try:
            round.get_current_player()
            self.fail()
        except m.RoundNotInProgressError:
            pass  # test succeeded

    def test_start_round_hand_modification(self):
        """
        The object should copy hands it takes in.
        """
        hands = u.deal_hands()
        round = HeartsRound(hands)

        # try to modify the hand we passed in
        hands[0].pop()

        # this should not have changed the given hand
        self.assertNotEqual(len(hands[0]), len(round.get_hand(0)))

    def test_start_round_get_hand_modification(self):
        """
        The object should copy hands it emits via get_hand
        """
        hands = u.deal_hands()
        round = HeartsRound(hands)

        hand = round.get_hand(0)
        hand.pop()

        # this should not have changed the given hand
        self.assertNotEqual(len(hand), len(round.get_hand(0)))

    def test_pass_cards_not_in_hand(self):
        """
        We should not be allowed to pass cards not in our hand.
        """
        round = HeartsRound(example_hands)

        cards_to_pass = ["h5", "h7", "sk"]  # sk is not in our hand

        try:
            round.pass_cards(0, cards_to_pass)
            self.fail()
        except m.CardsNotInHandError:
            pass  # test succeeded

    def test_pass_cards_twice(self):
        """
        We should not be allowed to pass cards more than once.
        """
        round = HeartsRound(example_hands)

        cards_to_pass = ["h5", "s7", "c2"]
        round.pass_cards(0, cards_to_pass)

        try:
            round.pass_cards(0, cards_to_pass)
            self.fail()
        except m.CardsAlreadyPassedError:
            pass  # test succeeded

    def test_finish_passing(self):
        """
        When all cards have been passed
        and we move to the playing state,
        the person with the two of clubs should be the first to play.
        """
        round = HeartsRound(example_hands)

        for i in range(4):
            round.pass_cards(i, example_hands[i][:3])

        round.finish_passing()

        self.assertEqual(1, round.get_current_player())

    def test_finish_passing_not_all_passed(self):
        """
        We should not be able to finish passing
        when not all players have passed.
        """
        round = HeartsRound(example_hands)

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
        round = HeartsRound(example_hands)

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

    def test_finish_passing_initial_player(self):
        """
        When all cards have been passed
        and we move to the playing state,
        the person with the two of clubs should be the first to play.
        """
        round = HeartsRound(example_hands)

        for i in range(4):
            round.pass_cards(i, example_hands[i][:3])

        round.finish_passing()

        self.assertEqual(1, round.get_current_player())

    def test_finish_passing_initial_player_2(self):
        """
        Same as previous test but with different player.
        """
        new_hands = [
            example_hands[1],
            example_hands[3],
            example_hands[0],
            example_hands[2]]

        round = HeartsRound(new_hands)

        for i in range(4):
            round.pass_cards(i, new_hands[i][-3:])

        round.finish_passing()

        self.assertEqual(2, round.get_current_player())


if __name__ == '__main__':
    unittest.main()
