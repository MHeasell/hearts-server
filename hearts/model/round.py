from exceptions import InvalidMoveError
import exceptions as e

import hearts.util as u


class HeartsRound(object):

    def __init__(self, hands):
        self.hands = [None, None, None, None]
        self.scores = [0, 0, 0, 0]
        self.current_player = None
        self.trick = []
        self.is_first_move = True
        self._is_hearts_broken = False
        self._is_first_trick = True
        self._observers = []

        for i, hand in enumerate(hands):
            self.hands[i] = list(hand)

        # find the starting player
        for i, hand in enumerate(self.hands):
            if "c2" in hand:
                self.current_player = i
                break

        if self.current_player is None:
            raise e.InvalidHandError

        assert self.current_player is not None

        # move to playing state
        self.is_first_move = True

    def add_observer(self, observer):
        self._observers.append(observer)

    def get_hand(self, player_index):
        return self.hands[player_index][:]

    def get_current_player(self):
        return self.current_player

    def get_score(self, player_index):
        return self.scores[player_index]

    def get_scores(self):
        return list(self.scores)

    def play_card(self, card):
        hand = self.hands[self.current_player]

        if card not in hand:
            raise InvalidMoveError()

        if self.is_first_move and card != "c2":
            raise InvalidMoveError()

        card_suit = u.get_suit(card)
        if len(self.trick) > 0:
            lead_suit = u.get_suit(self.trick[0]["card"])
            hand_has_suit = any(map(lambda c: u.get_suit(c) == lead_suit, hand))
            if hand_has_suit and lead_suit != card_suit:
                raise InvalidMoveError()

        if len(self.trick) == 0 and card_suit == "h" and not self._is_hearts_broken:
            raise InvalidMoveError()

        if card_suit == "h":
            self._is_hearts_broken = True

        if self._is_first_trick and (card_suit == "h" or card == "sq"):
            raise InvalidMoveError()

        player = self.current_player

        self.hands[player].remove(card)
        self.trick.append({"player": player, "card": card})
        self.current_player = (player + 1) % 4
        self.is_first_move = False

        for obs in self._observers:
            obs.on_play_card(player, card)

        if len(self.trick) == 4:
            self._finish_trick()

    def get_trick(self):
        return self.trick[:]

    def is_hearts_broken(self):
        return self._is_hearts_broken

    def is_first_trick(self):
        return self._is_first_trick

    def _finish_trick(self):
        # move onto the next trick
        cards = map(lambda x: x["card"], self.trick)
        win_idx = u.find_winning_index(cards)
        winner = self.trick[win_idx]["player"]
        self.current_player = winner
        self.trick = []
        self._is_first_trick = False
        points = u.sum_points(cards)
        self.scores[winner] += points

        for obs in self._observers:
            obs.on_finish_trick(winner, points)

        if all(map(lambda x: len(x) == 0, self.hands)):
            self._finish_round()

    def _finish_round(self):
        self._process_end_round_scores()

        for obs in self._observers:
            obs.on_finish_round(self.scores)

    def _process_end_round_scores(self):
        # check for shooting the moon
        # and adjust scores appropriately.
        moon_shooter = None
        for idx, score in enumerate(self.scores):
            if score == 26:
                moon_shooter = idx
                break

        if moon_shooter is not None:
            self.scores = [26, 26, 26, 26]
            self.scores[moon_shooter] = 0