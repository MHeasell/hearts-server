"""
This is the main model for the hearts game.
All the game domain logic lives here.
It only knows how to play hearts.
"""


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


class HeartsGame(object):

    def __init__(self):
        pass

    def get_score(self, player_index):
        return 0


class HeartsRound(object):

    def __init__(self, hands):
        self.hands = [None, None, None, None]
        self.passed_cards = [None, None, None, None]
        self.state = "passing"
        self.current_player = None

        for i, hand in enumerate(hands):
            self.hands[i] = list(hand)

    def get_hand(self, player_index):
        return self.hands[player_index][:]

    def get_current_player(self):
        if self.state == "passing":
            raise RoundNotInProgressError()

        return self.current_player

    def pass_cards(self, player_index, cards):
        if self.passed_cards[player_index] is not None:
            raise CardsAlreadyPassedError()

        # copy cards to prevent shenanigans
        cards_to_pass = list(cards)

        for card in cards_to_pass:
            if card not in self.hands[player_index]:
                raise CardsNotInHandError()

        self.passed_cards[player_index] = cards_to_pass

    def finish_passing(self):
        for cards in self.passed_cards:
            if cards is None:
                raise PlayersYetToPassError()

        for i, cards in enumerate(self.passed_cards):
            for card in cards:
                self.hands[i].remove(card)
                self.hands[(i + 1) % 4].append(card)

        # find the starting player
        for i, hand in enumerate(self.hands):
            if "c2" in hand:
                self.current_player = i
                break

        assert self.current_player is not None

        # move to playing state
        self.state = "playing"
