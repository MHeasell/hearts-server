from exceptions import CardsAlreadyPassedError
from exceptions import CardsNotInHandError
from exceptions import PlayersYetToPassError

import hearts.util as u


class HeartsPreRound(object):
    def __init__(self, hands, pass_direction="left"):
        self.pass_direction = pass_direction
        self.hands = [None, None, None, None]
        self.passed_cards = [None, None, None, None]

        for i, hand in enumerate(hands):
            self.hands[i] = list(hand)

    def get_hand(self, player_index):
        return self.hands[player_index][:]

    def get_all_hands(self):
        hands = [None, None, None, None]
        for i, hand in enumerate(self.hands):
            hands[i] = list(hand)
        return hands

    def have_all_passed(self):
        return all(self.passed_cards)

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
                target_index = self._get_target_player_index(i)
                self.hands[i].remove(card)
                self.hands[target_index].append(card)

    def _get_target_player_index(self, player_index):
        return (player_index + u.get_pass_offset(self.pass_direction)) % 4
