import unittest
from mock import Mock

from hearts.model.game import HeartsGame
import hearts.model.exceptions as e

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

    def test_init_pass_cards(self):
        """
        When the game is first initialized
        passing cards should throw an exception.
        """
        game = HeartsGame()

        try:
            game.pass_cards(0, ["c2", "c3", "c4"])
            self.fail()
        except e.PassingNotInProgressError:
            pass  # test succeeded

    def test_init_get_pass_direction(self):
        game = HeartsGame()

        try:
            game.get_pass_direction()
            self.fail()
        except e.PassingNotInProgressError:
            pass  # test succeeded

    def test_init_get_hand(self):
        game = HeartsGame()
        try:
            game.get_hand(0)
            self.fail()
        except e.RoundNotInProgressError:
            pass  # test succeeded

    def test_init_get_current_player(self):
        game = HeartsGame()
        try:
            game.get_current_player()
            self.fail()
        except e.RoundNotInProgressError:
            pass  # test succeeded

    def test_init_play_card(self):
        game = HeartsGame()
        try:
            game.play_card("c2")
            self.fail()
        except e.RoundNotInProgressError:
            pass  # test succeeded

    def test_init_get_state(self):
        game = HeartsGame()
        self.assertEqual("init", game.get_state())

    def test_start_game(self):
        """
        When the game is started,
        listeners should be notified.
        """
        game = HeartsGame()
        observer = Mock()
        game.add_observer(observer)

        game.start()

        observer.on_start_round.assert_called_once_with(0)

    def test_start_game_twice(self):
        """
        Tests that we can't call start() more than once.
        """
        game = HeartsGame()
        game.start()

        try:
            game.start()
            self.fail()
        except e.GameAlreadyStartedError:
            pass  # test succeeded

    def test_start_game_preround(self):
        """
        When the game is started,
        it should go into the first pre-round,
        passing left.
        """
        game = HeartsGame(deal_func=lambda: example_hands)
        observer = Mock()
        game.add_observer(observer)

        game.start()

        self.assertEqual("passing", game.get_state())
        self.assertEqual("left", game.get_pass_direction())
        self.assertEqual(example_hands[0], game.get_hand(0))

    def test_finish_passing(self):
        """
        Tests that the state transitions properly
        into playing when passing is finished.
        """
        game = HeartsGame(deal_func=lambda: example_hands)
        observer = Mock()
        game.add_observer(observer)

        game.start()

        for i in range(4):
            game.pass_cards(i, example_hands[i][:3])

        self.assertEqual("playing", game.get_state())
        self.assertEqual(1, game.get_current_player())
        new_hand = example_hands[0][:3] + example_hands[1][3:]
        self.assertEqual(set(new_hand), set(game.get_hand(1)))

    def test_play_card(self):
        game = HeartsGame(deal_func=lambda: example_hands)
        observer = Mock()
        game.add_observer(observer)

        game.start()

        for i in range(4):
            game.pass_cards(i, example_hands[i][:3])

        game.play_card("c2")

        self.assertEqual([{"player": 1, "card": "c2"}], game.get_trick())

    def test_finish_trick(self):
        """
        Tests that observers are notified
        when a trick is finished.
        """
        game = HeartsGame(deal_func=lambda: example_hands)

        game.start()

        for i in range(4):
            game.pass_cards(i, example_hands[i][:3])

        observer = Mock()
        game.add_observer(observer)

        # player 1 starts
        game.play_card("c2")
        game.play_card("c10")
        game.play_card("c6")
        game.play_card("c4")

        observer.on_finish_trick.assert_called_once_with(2, 0)

    def test_finish_round(self):
        """
        Tests that when the round is finished,
        the scores are updated,
        observers are notified
        and a new round starts.
        """

        # we're going to cheat and deal only three cards
        # to each player
        hands = [
            ["c2", "c3", "ck"],
            ["c5", "c6", "h2"],
            ["c7", "c8", "h3"],
            ["c9", "c10", "sq"]
        ]

        game = HeartsGame(deal_func=lambda: hands)
        game.start()
        for i in range(4):
            game.pass_cards(i, hands[i])

        self.assertEqual(1, game.get_current_player())

        game.play_card("c2")
        game.play_card("c5")
        game.play_card("c7")
        game.play_card("c9")

        self.assertEqual(0, game.get_current_player())

        game.play_card("sq")
        game.play_card("c3")
        game.play_card("c6")
        game.play_card("c8")

        # player 0 wins this hand, getting 13 points
        self.assertEqual(13, game.get_round_score(0))
        self.assertEqual(0, game.get_current_player())

        observer = Mock()
        game.add_observer(observer)

        game.play_card("c10")
        game.play_card("ck")
        game.play_card("h2")
        game.play_card("h3")

        # player 1 wins this hand, getting 2 points

        # the round should now be over
        # and a new round should start
        self.assertEqual(1, game.get_current_round_number())
        self.assertEqual(13, game.get_score(0))
        self.assertEqual(2, game.get_score(1))
        self.assertEqual([13, 2, 0, 0], game.get_scores())
        observer.on_finish_round.assert_called_once_with([13, 2, 0, 0])
        observer.on_start_round.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()