import unittest

from hearts.model.game import HeartsGame


class TestHeartsModel(unittest.TestCase):

    def test_init_scores(self):
        """
        When the game is first initialized,
        the score for each player should be zero.
        """
        game = HeartsGame()

        for i in range(4):
            self.assertEqual(0, game.get_score(i))


if __name__ == "__main__":
    unittest.main()