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
        self._current_round = None

    def get_score(self, player_index):
        return 0

    def get_scores(self):
        return [0, 0, 0, 0]

    def get_current_round_number(self):
        if self._state != "playing" and self._state != "passing":
            raise e.RoundNotInProgressError()

        return self._current_round

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

    def is_hearts_broken(self):
        if self._state != "playing":
            raise e.RoundNotInProgressError()

        return self._round.is_hearts_broken()

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

        self._start_round()

    def _start_round(self):
        if self._current_round is None:
            self._current_round = 0
        else:
            self._current_round += 1

        hands = self._deal_func()

        if self._current_round % 4 == 0:
            self._start_playing(hands)
        else:
            self._start_preround(hands)

        for obs in self._observers:
            obs.on_start_round(self._current_round)

    def _start_preround(self, hands):
        self._state = "passing"
        pass_direction = self._get_pass_direction()
        self._preround = HeartsPreRound(hands, pass_direction)

    def _start_playing(self, hands):
        self._state = "playing"
        self._round = HeartsRound(hands)
        self._round.add_observer(RoundObserver(self))

    def _finish_preround(self):
        self._preround.finish_passing()
        for obs in self._observers:
            obs.on_finish_passing()

        self._start_playing(self._preround.get_all_hands())

    def _get_pass_direction(self):
        return ["left", "right", "across", "none"][self._current_round % 4]

    def _on_play_card(self, player_index, card):
        for obs in self._observers:
            obs.on_play_card(player_index, card)

    def _on_finish_trick(self, winner, points):
        for obs in self._observers:
            obs.on_finish_trick(winner, points)


class RoundObserver(object):
    def __init__(self, game):
        self.game = game

    def on_play_card(self, player, card):
        self.game._on_play_card(player, card)

    def on_finish_trick(self, winner, points):
        self.game._on_finish_trick(winner, points)
