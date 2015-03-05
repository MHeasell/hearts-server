import unittest

from hearts.game_model import HeartsGame
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

    def test_init_hands(self):
        """
        When the game is first initialized,
        getting someone's hand should fail,
        as no round has started yet.
        """
        game = HeartsGame()

        for i in range(4):
            try:
                game.get_hand(i)
                self.fail()
            except m.RoundNotInProgressError:
                pass  # test succeeded

    def test_init_pass_cards(self):
        """
        When the game is first initialized,
        passing someone cards should fail,
        as no round has started yet.
        """
        game = HeartsGame()

        for i in range(4):
            try:
                game.pass_cards(0, ["c2", "c3", "c4"])
                self.fail()
            except m.RoundNotInProgressError:
                pass  # test succeeded

    def test_init_get_current_player(self):
        """
        When the game is first initialized,
        get_current_player should fail
        as no round has started yet.
        """
        game = HeartsGame()

        try:
            game.get_current_player()
            self.fail()
        except m.RoundNotInProgressError:
            pass  # test succeeded

    def test_start_round(self):
        """
        When we start a round, giving everyone their hands,
        they should have those cards in their hand.
        """
        game = HeartsGame()

        hands = u.deal_hands()

        game.start_round(hands)

        for i in range(4):
            self.assertEqual(hands[i], game.get_hand(i))

    def test_start_round_hand_modification(self):
        """
        The object should copy hands it takes in.
        """
        game = HeartsGame()
        hands = u.deal_hands()
        game.start_round(hands)

        # try to modify the hand we passed in
        hands[0].pop()

        # this should not have changed the given hand
        self.assertNotEqual(len(hands[0]), len(game.get_hand(0)))

    def test_start_round_get_hand_modification(self):
        """
        The object should copy hands it emits via get_hand
        """
        game = HeartsGame()
        hands = u.deal_hands()
        game.start_round(hands)

        hand = game.get_hand(0)
        hand.pop()

        # this should not have changed the given hand
        self.assertNotEqual(len(hand), len(game.get_hand(0)))

    def test_pass_cards_not_in_hand(self):
        """
        We should not be allowed to pass cards not in our hand.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        cards_to_pass = ["h5", "h7", "sk"]  # sk is not in our hand

        try:
            game.pass_cards(0, cards_to_pass)
            self.fail()
        except m.CardsNotInHandError:
            pass  # test succeeded

    def test_pass_cards_twice(self):
        """
        We should not be allowed to pass cards more than once.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        cards_to_pass = ["h5", "s7", "c2"]
        game.pass_cards(0, cards_to_pass)

        try:
            game.pass_cards(0, cards_to_pass)
            self.fail()
        except m.CardsAlreadyPassedError:
            pass  # test succeeded

    def test_passing_get_current_player(self):
        """
        When players are passing cards to each other,
        get_current_player should fail
        as the round is not in play.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        try:
            game.get_current_player()
            self.fail()
        except m.RoundNotInProgressError:
            pass  # test succeeded

    def test_finish_passing(self):
        """
        When all cards have been passed
        and we move to the playing state,
        the person with the two of clubs should be the first to play.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        for i in range(4):
            game.pass_cards(i, example_hands[i][:3])

        game.finish_passing()

        self.assertEqual(1, game.get_current_player())

    def test_finish_passing_not_all_passed(self):
        """
        We should not be able to finish passing
        when not all players have passed.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        # last player does not pass
        for i in range(3):
            game.pass_cards(i, example_hands[i][:3])

        try:
            game.finish_passing()
            self.fail()
        except m.PlayersYetToPassError:
            pass  # test succeeded

    def test_finish_passing_update_hands(self):
        """
        When passing is finished,
        passed cards should be transferred to players' hands.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        for i in range(4):
            game.pass_cards(i, example_hands[i][:3])

        game.finish_passing()

        for card in example_hands[0][:3]:
            self.assertNotIn(card, game.get_hand(0))
            self.assertIn(card, game.get_hand(1))

        for card in example_hands[1][:3]:
            self.assertNotIn(card, game.get_hand(1))
            self.assertIn(card, game.get_hand(2))

        for card in example_hands[2][:3]:
            self.assertNotIn(card, game.get_hand(2))
            self.assertIn(card, game.get_hand(3))

        for card in example_hands[3][:3]:
            self.assertNotIn(card, game.get_hand(3))
            self.assertIn(card, game.get_hand(0))

    def test_finish_passing_initial_player(self):
        """
        When all cards have been passed
        and we move to the playing state,
        the person with the two of clubs should be the first to play.
        """
        game = HeartsGame()
        game.start_round(example_hands)

        for i in range(4):
            game.pass_cards(i, example_hands[i][:3])

        game.finish_passing()

        self.assertEqual(1, game.get_current_player())

    def test_finish_passing_initial_player_2(self):
        """
        Same as previous test but with different player.
        """
        game = HeartsGame()
        new_hands = [
            example_hands[1],
            example_hands[3],
            example_hands[0],
            example_hands[2]]

        game.start_round(new_hands)

        for i in range(4):
            game.pass_cards(i, new_hands[i][-3:])

        game.finish_passing()

        self.assertEqual(2, game.get_current_player())

if __name__ == '__main__':
    unittest.main()
