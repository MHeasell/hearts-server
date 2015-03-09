import unittest

from hearts.model.round import HeartsRound
from hearts.model.preround import HeartsPreRound
import hearts.util as u
import hearts.model.exceptions as m

example_hands = [
    ['h5', 's7', 'c2', 'h1', 'd2', 'h8', 'd3', 's2', 'd9', 'c5', 'd8', 'dq', 'c4'],
    ['c10', 'h6', 'c3', 'h10', 'hk', 'd7', 'dk', 'h4', 'sj', 'hq', 'hj', 's5', 'd5'],
    ['s6', 's10', 'd1', 'sk', 's4', 'h7', 'd10', 'sq', 'c9', 'cq', 'd6', 'h2', 'cj'],
    ['d4', 'c8', 'h9', 'ck', 'h3', 'c6', 'dj', 's9', 's1', 'c1', 's3', 'c7', 's8']
]


class TestHeartsRound(unittest.TestCase):

    def test_init(self):
        round = HeartsRound(example_hands)
        for i in range(4):
            self.assertEqual(example_hands[i], round.get_hand(i))

    def test_init_play_is_hearts_broken(self):
        """
        When play initially starts, hearts should not be broken.
        """
        round = HeartsRound(example_hands)
        self.assertFalse(round.is_hearts_broken())

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

    def test_finish_passing_initial_player(self):
        """
        The person with the two of clubs should be the first to play.
        """
        round = HeartsRound(example_hands)

        self.assertEqual(0, round.get_current_player())

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

        self.assertEqual(2, round.get_current_player())

    def test_get_trick_mod(self):
        """
        We should not be able to modify the trick once returned.
        """
        round = HeartsRound(example_hands)
        trick = round.get_trick()
        trick.append("foo")
        self.assertNotEqual(len(trick), len(round.get_trick()))

    def test_play_move(self):
        """
        The leading player should be able to play a card,
        which should get put onto the trick.
        """
        round = HeartsRound(example_hands)

        round.play_card("c2")

        expected = [{"player": 0, "card": "c2"}]

        self.assertEquals(expected, round.get_trick())

    def test_play_move_2(self):
        """
        Same as before, but no passing and different leading player
        """
        new_hands = [example_hands[1], example_hands[0], example_hands[2], example_hands[3]]
        round = HeartsRound(new_hands)

        round.play_card("c2")

        expected = [{"player": 1, "card": "c2"}]

        self.assertEquals(expected, round.get_trick())

    def test_play_move_current_player(self):
        """
        When a move has been played, the current player should update.
        """
        round = HeartsRound(example_hands)

        self.assertEqual(0, round.get_current_player())

        round.play_card("c2")

        self.assertEqual(1, round.get_current_player())

    def test_play_move_current_player_rollover(self):
        """
        The current player should roll over to player 0
        after player 3 plays a card.
        """
        hands = [example_hands[1], example_hands[2], example_hands[3], example_hands[0]]
        round = HeartsRound(hands)

        self.assertEqual(3, round.get_current_player())
        round.play_card("c2")
        self.assertEqual(0, round.get_current_player())

    def test_play_first_move_not_two_of_clubs(self):
        """
        The first card of the round should always be the two of clubs.
        """
        round = HeartsRound(example_hands)

        try:
            round.play_card("c5")
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_play_second_move(self):
        """
        After the first move, the second player can play any club
        """
        round = HeartsRound(example_hands)

        round.play_card("c2")
        round.play_card("c10")

        expected = [
            {"player": 0, "card": "c2"},
            {"player": 1, "card": "c10"}
        ]

        self.assertEqual(expected, round.get_trick())

    def test_play_second_move_bad_suit(self):
        """
        After the first move, the second player must play a club,
        not any other suit.
        """
        round = HeartsRound(example_hands)

        round.play_card("c2")

        try:
            round.play_card("d7")
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_finish_trick(self):
        """
        Tests that the next trick is set up properly
        when a trick is finished.
        """
        round = HeartsRound(example_hands)

        # play the trick
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("c9")
        round.play_card("c8")

        # player 1 was the winner,
        # so we expect them to be the current player
        self.assertEqual(1, round.get_current_player())

        # the trick should be empty now
        self.assertEqual([], round.get_trick())

    def test_finish_trick_winner(self):
        """
        Tests that the winner of the trick is properly set.
        """
        round = HeartsRound(example_hands)

        # play the trick
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("cq")
        round.play_card("c8")

        # player 2 was the winner,
        # so we expect them to be the current player
        self.assertEqual(2, round.get_current_player())

    def test_play_follow_suit_not_clubs(self):
        """
        Players must follow suit
        whatever suit the first card is.
        """
        round = HeartsRound(example_hands)

        # get the first trick out of the way
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("c9")
        round.play_card("c8")

        # player one wins, they lead
        round.play_card("d7")

        try:
            # player two tries to play a non-diamond card
            round.play_card("cq")
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_play_card_not_in_hand(self):
        """
        Tests that a player can only play cards
        that are in their hand.
        """
        round = HeartsRound(example_hands)

        round.play_card("c2")

        try:
            # this card is not in player 1's hand
            round.play_card("c5")
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_play_card_already_played(self):
        """
        Tests that a player cannot play a card
        that they already played on a previous trick.
        """
        round = HeartsRound(example_hands)

        # get the first trick out of the way
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("c9")
        round.play_card("c8")

        # player 1 wins, next trick
        try:
            # player 1 already played this card
            round.play_card("c10")
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_play_heart_not_broken(self):
        """
        Tests that a player cannot lead with a heart
        when hearts has not been broken.
        """
        round = HeartsRound(example_hands)

        # get the first trick out of the way
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("c9")
        round.play_card("c8")

        # player 1 wins, next trick
        try:
            round.play_card("h6")
            self.fail()
        except m.InvalidMoveError:
            pass  # test succeeded

    def test_play_cannot_follow_suit(self):
        """
        Tests that a player can play a card of a different suit
        if they cannot follow suit.
        """
        pre = HeartsPreRound(example_hands, "left")

        pre.pass_cards(0, ["s7", "c5", "c4"])
        pre.pass_cards(1, ["hj", "s5", "d5"])
        pre.pass_cards(2, ["d6", "h2", "sq"])
        pre.pass_cards(3, ["d4", "dj", "s9"])
        pre.finish_passing()

        round = HeartsRound(pre.get_all_hands())

        # get the first trick out of the way
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("c9")
        round.play_card("c8")

        # player 1 to start now
        self.assertEqual(1, round.get_current_player())

        round.play_card("c3")
        round.play_card("cj")
        round.play_card("c7")
        round.play_card("dq")  # player 0 has no clubs

        # player 2 wins due to cj
        self.assertEqual(2, round.get_current_player())

    def test_play_break_hearts(self):
        """
        Tests that once hearts is broken,
        it is possible to lead with a heart.
        """
        pre = HeartsPreRound(example_hands, "left")
        pre.pass_cards(0, ["s7", "c5", "c4"])
        pre.pass_cards(1, ["hj", "s5", "d5"])
        pre.pass_cards(2, ["d6", "h2", "sq"])
        pre.pass_cards(3, ["d4", "dj", "s9"])
        pre.finish_passing()

        round = HeartsRound(pre.get_all_hands())

        # get the first trick out of the way
        round.play_card("c2")
        round.play_card("c10")
        round.play_card("c9")
        round.play_card("c8")

        # player 1 to start now
        self.assertEqual(1, round.get_current_player())

        round.play_card("c3")
        round.play_card("cj")
        round.play_card("c7")
        round.play_card("h5")  # player 0 has no clubs

        # player 2 wins due to cj
        self.assertEqual(2, round.get_current_player())

        # check that hearts is broken
        self.assertTrue(round.is_hearts_broken())

        # player 2 can lead with a heart now
        round.play_card("h7")

        self.assertEqual([{"player": 2, "card": "h7"}], round.get_trick())

    def test_play_first_trick_break_hearts(self):
        """
        Tests that hearts cannot be played on the first trick
        """
        pre = HeartsPreRound(example_hands, "left")
        pre.pass_cards(0, ["c2", "c5", "c4"])
        pre.pass_cards(1, ["hj", "s5", "d5"])
        pre.pass_cards(2, ["d6", "h2", "sq"])
        pre.pass_cards(3, ["d4", "dj", "s9"])
        pre.finish_passing()

        round = HeartsRound(pre.get_all_hands())

        # player 1 has the c2, so they start
        round.play_card("c2")
        round.play_card("c9")
        round.play_card("c8")

        try:
            # player 0 has no clubs,
            # but they cannot play a heart on the first trick
            round.play_card("h5")
            self.fail()
        except m.InvalidMoveError:
            pass

    def test_play_first_trick_queen_of_spades(self):
        """
        Tests that the queen of spades cannot be played on the first trick
        """
        pre = HeartsPreRound(example_hands, "across")
        pre.pass_cards(0, ["c2", "c5", "c4"])
        pre.pass_cards(1, ["hj", "s5", "d5"])
        pre.pass_cards(2, ["d6", "h2", "sq"])
        pre.pass_cards(3, ["d4", "dj", "s9"])
        pre.finish_passing()

        round = HeartsRound(pre.get_all_hands())
        # player 2 has the c2, so they start
        round.play_card("c2")
        round.play_card("c8")

        try:
            # player 0 has no clubs,
            # but they cannot play the queen of spades on the first trick
            round.play_card("sq")
            self.fail()
        except m.InvalidMoveError:
            pass


if __name__ == '__main__':
    unittest.main()
