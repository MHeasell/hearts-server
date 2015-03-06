"""
This is the main model for the hearts game.
All the game domain logic lives here.
It only knows how to play hearts.
"""

import hearts.util as u


class GameStateError(Exception):
    pass


class RoundNotInProgressError(GameStateError):
    pass


class IncorrectPassPlayerError(GameStateError):
    pass


class CardsNotInHandError(GameStateError):
    pass


class CardsAlreadyPassedError(GameStateError):
    pass


class PlayersYetToPassError(GameStateError):
    pass


class PassingNotInProgressError(GameStateError):
    pass


class InvalidMoveError(GameStateError):
    pass


class HeartsGame(object):

    def __init__(self):
        pass

    def get_score(self, player_index):
        return 0


class HeartsRound(object):

    def __init__(self, hands, pass_direction="left"):
        self.hands = [None, None, None, None]
        self.passed_cards = [None, None, None, None]
        self.state = "init"
        self.current_player = None
        self.pass_direction = pass_direction
        self.trick = []
        self.is_first_move = True

        for i, hand in enumerate(hands):
            self.hands[i] = list(hand)

        if pass_direction != "none":
            self._start_passing()
        else:
            self._start_playing()

    def get_hand(self, player_index):
        return self.hands[player_index][:]

    def get_current_player(self):
        if self.state == "passing":
            raise RoundNotInProgressError()

        return self.current_player

    def pass_cards(self, player_index, cards):
        if self.state != "passing":
            raise PassingNotInProgressError()

        if self.passed_cards[player_index] is not None:
            raise CardsAlreadyPassedError()

        # copy cards to prevent shenanigans
        cards_to_pass = list(cards)

        for card in cards_to_pass:
            if card not in self.hands[player_index]:
                raise CardsNotInHandError()

        self.passed_cards[player_index] = cards_to_pass

    def finish_passing(self):
        if self.state != "passing":
            raise PassingNotInProgressError()

        self._finish_passing()
        self._start_playing()

    def play_card(self, card):
        if self.state != "playing":
            raise RoundNotInProgressError()

        if self.is_first_move and card != "c2":
            raise InvalidMoveError()

        if u.get_suit(card) != "c":
            raise InvalidMoveError()
        #if len(self.trick) > 0 and u.get_suit(card) != u.get_suit(self.trick[0]["card"]):
        #    raise InvalidMoveError()

        self.trick.append({"player": self.current_player, "card": card})
        self.current_player = (self.current_player + 1) % 4
        self.is_first_move = False

    def get_trick(self):
        if self.state != "playing":
            raise RoundNotInProgressError()

        return self.trick[:]

    def _start_passing(self):
        self.passed_cards = [None, None, None, None]
        self.state = "passing"

    def _finish_passing(self):
        for cards in self.passed_cards:
            if cards is None:
                raise PlayersYetToPassError()

        for i, cards in enumerate(self.passed_cards):
            for card in cards:
                target_index = self._get_target_player_index(i)
                self.hands[i].remove(card)
                self.hands[target_index].append(card)

    def _start_playing(self):
        # find the starting player
        for i, hand in enumerate(self.hands):
            if "c2" in hand:
                self.current_player = i
                break

        assert self.current_player is not None

        # move to playing state
        self.state = "playing"
        self.is_first_move = True

    def _get_target_player_index(self, player_index):
        return (player_index + u.get_pass_offset(self.pass_direction)) % 4
