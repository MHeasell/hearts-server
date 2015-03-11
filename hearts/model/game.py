import exceptions as e
from preround import HeartsPreRound
from round import HeartsRound

import hearts.util as u


class HeartsGame(object):

    def __init__(self, deal_func=u.deal_hands):
        self._observers = []
        self._state = "init"
        self._preround = None
        self._deal_func = deal_func

    def get_score(self, player_index):
        return 0

    def get_scores(self):
        return [0, 0, 0, 0]

    def get_round_score(self, player_index):
        if self._state != "playing":
            raise e.RoundNotInProgressError()

        return self._round.get_score(player_index)

    def get_round_scores(self):
        if self._state != "playing":
            raise e.RoundNotInProgressError()

        return self._round.get_scores()

    def get_state(self):
        return self._state

    def get_hand(self, player_index):
        if self._state == "passing":
            return self._preround.get_hand(player_index)

        if self._state == "playing":
            return self._round.get_hand(player_index)

        raise e.RoundNotInProgressError()

    def get_current_player(self):
        if self._state == "playing":
            return self._round.get_current_player()

        raise e.RoundNotInProgressError()

    def get_trick(self):
        if self._state == "playing":
            return self._round.get_trick()

        raise e.RoundNotInProgressError()

    def get_pass_direction(self):
        if self._state != "passing":
            raise e.PassingNotInProgressError()

        return self._preround.pass_direction

    def get_received_cards(self, player_index):
        if self._state != "passing":
            raise e.PassingNotInProgressError()

        return self._preround.get_received_cards(player_index)

    def has_player_passed(self, player_index):
        if self._state != "passing":
            raise e.PassingNotInProgressError()

        return self._preround.has_player_passed(player_index)

    def pass_cards(self, player_index, cards):
        if self._state != "passing":
            raise e.PassingNotInProgressError()

        self._preround.pass_cards(player_index, cards)
        if self._preround.have_all_passed():
            self._finish_preround()

    def _finish_preround(self):
        self._preround.finish_passing()
        for obs in self._observers:
            obs.on_finish_preround()

        self._start_playing(self._preround.get_all_hands())

    def _start_playing(self, hands):
        self._state = "playing"
        self._round = HeartsRound(hands)
        self._round.add_observer(RoundObserver(self))

        for obs in self._observers:
            obs.on_start_playing()

    def play_card(self, card):
        if self._state != "playing":
            raise e.RoundNotInProgressError()

        self._round.play_card(card)

    def add_observer(self, observer):
        self._observers.append(observer)

    def remove_observer(self, observer):
        self._observers.remove(observer)

    def start(self):
        for obs in self._observers:
            obs.on_start()

        self._start_preround()

    def _start_preround(self):
        self._state = "passing"
        self._preround = HeartsPreRound(self._deal_func(), "left")

        for obs in self._observers:
            obs.on_start_preround("left")

    def _on_finish_trick(self, winner, points):
        for obs in self._observers:
            obs.on_finish_trick(winner, points)


class RoundObserver(object):
    def __init__(self, game):
        self.game = game

    def on_finish_trick(self, winner, points):
        self.game._on_finish_trick(winner, points)
