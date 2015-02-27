from uuid import uuid4
import json

from redis import WatchError

from hearts.util import redis_key
from hearts.keys import GAME_EVENTS_QUEUE_KEY, QUEUE_KEY

from hearts.services.player import PlayerStateError

import time


class AccessDeniedError(Exception):
    pass


class GameStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


class GameEventQueueService(object):

    def __init__(self, redis):
        self.redis = redis

    def blocking_pop_event(self):
        elem = self.redis.brpop([GAME_EVENTS_QUEUE_KEY])[1]
        params = elem.split(",")
        return params

    def raise_init_event(self, game_id):
        self._raise_event("init", game_id)

    def raise_start_round_event(self, game_id, round_number):
        self._raise_event("start_round", game_id, round_number)

    def raise_end_round_event(self, game_id, round_number):
        self._raise_event("end_round", game_id, round_number)

    def raise_end_game_event(self, game_id):
        self._raise_event("end_game", game_id)

    def _raise_event(self, *data):
        self.redis.lpush(GAME_EVENTS_QUEUE_KEY, ",".join(map(str, data)))


def _players_key(game_id):
        return redis_key("game", game_id, "players")


def _score_key(game_id, player):
    return redis_key("game", game_id, "players", player, "score")


def _events_key(game_id):
    return redis_key("game", game_id, "events")


def _last_event_key(game_id):
    return redis_key("game", game_id, "last_event")


def _push_event(pipe, game_id, event_type, **event_keys):
    timestamp = time.time()
    event_json = json.dumps(
        type=event_type,
        timestamp=timestamp,
        **event_keys)

    key = _events_key(game_id)
    pipe.zadd(key, timestamp, event_json)
    pipe.set(_last_event_key(game_id), timestamp)


class GameService(object):

    def __init__(self, redis):
        self.redis = redis

    def create_game(self, players):
        game_id = str(uuid4())

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    # guard against queue changes
                    pipe.watch(QUEUE_KEY)

                    # check that the players are in the queue
                    for player in players:
                        if pipe.zscore(QUEUE_KEY, player) is None:
                            raise PlayerStateError("Player is not in the queue.")

                    pipe.multi()

                    # add the players to the game players list
                    pipe.rpush(_players_key(game_id), *players)

                    # set each player's current game to this
                    for player in players:
                        key = redis_key("player", player, "current_game")
                        pipe.set(key, game_id)

                    # remove the players from the queue
                    pipe.zrem(QUEUE_KEY, *players)

                    pipe.execute()

                    return game_id

                except WatchError:
                    continue

    def get_players(self, game_id):
        """
        Fetches the list of players for the game.
        :return: The list of players.
        If the game does not exist, the list will be empty.
        """
        return self.redis.lrange(_players_key(game_id), 0, -1)

    def set_current_round(self, game_id, round_number):
        key = redis_key("game", game_id, "current_round")
        self.redis.set(key, round_number)

    def get_round_service(self, game_id, round_number):
        return GameRoundService(self.redis, game_id, round_number)

    def add_to_scores(self, game_id, score_dict):
        players = score_dict.keys()
        with self.redis.pipeline() as pipe:
            for player in players:
                key = _score_key(game_id, player)
                pipe.incrby(key, score_dict[player])
            new_scores = pipe.execute()

        return dict(zip(players, new_scores))

    def get_events(self, game_id):
        return self.redis.zrange(_events_key(game_id), 0, -1)

    def get_event(self, game_id, idx):
        idx -= 1  # convert to zero-based index
        events = self.redis.zrange(_events_key(game_id), idx, idx)
        if events is None or len(events) < 1:
            return None
        return events[0]

    def log_round_start_event(self, game_id, round_number):
        self._log_event(game_id, "round_start", round_number=round_number)

    def log_round_passing_completed_event(self, game_id, round_number):
        self._log_event(game_id, "passing_completed", round_number=round_number)

    def log_play_card_event(self, game_id, round_number, pile_number, card_number, player, card):
        self._log_event(
            game_id,
            "play_card",
            round_number=round_number,
            pile_number=pile_number,
            card_number=card_number,
            player=player,
            card=card)

    def _log_event(self, game_id, event_type, **data):
        _push_event(self.redis, game_id, event_type, **data)


class GameRoundService(object):
    def __init__(self, redis, game_id, round_number):
        self.redis = redis
        self.game_id = game_id
        self.round_number = round_number

    def set_hands(self, players, hands):
        with self.redis.pipeline() as pipe:
            # set everyone's hand
            for (player, hand) in zip(players, hands):
                pipe.sadd(self._hand_key(player), *hand)

            pipe.execute()

    def get_hand(self, player_name):
        """
        Fetches the set of cards in the player's hand.
        :param player_name: The name of the player whose hand we should fetch.
        :return: A set instance containing the cards in the hand.
        """
        key = self._hand_key(player_name)
        return self.redis.smembers(key)

    def has_received_cards(self, player_name):
        key = self._received_cards_key(player_name)

        return self.redis.scard(key) > 0

    def get_passed_cards(self, player_name):
        """
        Fetches the cards that this player was passed.
        Returns empty set if there are no cards yet.
        :param player_name: The name of the player.
        :return: The set of passed cards.
        """
        key = self._received_cards_key(player_name)
        return self.redis.smembers(key)

    def have_all_received_cards(self, *players):
        with self.redis.pipeline() as pipe:
            for player in players:
                pipe.get(self._received_key(player))
            result = pipe.execute()

        for r in result:
            if not r:
                return False

        return True

    def pass_cards(self, from_player, to_player, cards):
        requester_hand_key = self._hand_key(from_player)
        target_passed_cards_key = self._received_cards_key(to_player)

        requester_has_passed_key = self._passed_key(from_player)
        target_has_received_key = self._received_key(to_player)

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    # Make sure the cards don't change while we're doing this
                    pipe.watch(requester_hand_key)
                    pipe.watch(target_passed_cards_key)

                    # check that the target player has not already
                    # been given cards
                    if pipe.scard(target_passed_cards_key) != 0:
                        err = "Player {0} has already been passed cards."
                        raise GameStateError(err.format(to_player))

                    # check that the cards are in the requester's hand
                    for c in cards:
                        if not pipe.sismember(requester_hand_key, c):
                            err = "{0}'s hand does not contain card {1}."
                            raise GameStateError(err.format(from_player, c))

                    pipe.multi()

                    # remove the cards from the requester's hand
                    pipe.srem(requester_hand_key, *cards)

                    # add the cards to the target's passed cards collection
                    pipe.sadd(target_passed_cards_key, *cards)

                    # mark each player has having passed/received
                    pipe.set(requester_has_passed_key, True)
                    pipe.set(target_has_received_key, True)

                    pipe.execute()

                    break

                except WatchError:
                    continue

    def play_card(self, pile_number, player, card):
        pile_key = self._pile_key(pile_number)
        player_hand_key = self._hand_key(player)
        passed_cards_key = self._received_cards_key(player)

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(player_hand_key)
                    pipe.watch(passed_cards_key)
                    pipe.watch(pile_key)

                    if not pipe.sismember(player_hand_key, card) \
                            and not pipe.sismember(passed_cards_key, card):
                        err = "{0}'s hand does not contain card {1}."
                        raise GameStateError(err.format(player, card))

                    if pipe.llen(pile_key) > 4:
                        raise GameStateError("The pile is full.")

                    blob = json.dumps({"player": player, "card": card})

                    pipe.multi()
                    pipe.srem(player_hand_key, card)
                    pipe.srem(passed_cards_key, card)
                    pipe.rpush(pile_key, blob)
                    pipe.llen(pile_key)
                    pile_length = pipe.execute()[3]

                    return pile_length

                except WatchError:
                    continue

    def get_pile(self, pile_number):
        key = self._pile_key(pile_number)
        return self.redis.lrange(key, 0, -1)

    def get_pile_card(self, pile_number, card_number):
        key = self._pile_key(pile_number)
        return self.redis.lindex(key, card_number - 1)

    def get_all_piles(self):
        with self.redis.pipeline() as pipe:
            for i in xrange(1, 14):
                pipe.lrange(self._pile_key(i), 0, -1)

            return pipe.execute()

    def _pile_key(self, pile_number):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            self.round_number,
            "piles",
            pile_number)

    def _hand_key(self, player):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            self.round_number,
            "players",
            player,
            "hand")

    def _received_cards_key(self, player):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            self.round_number,
            "players",
            player,
            "passed_cards")

    def _received_key(self, player):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            self.round_number,
            "players",
            player,
            "has_received_cards")

    def _passed_key(self, player):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            self.round_number,
            "players",
            player,
            "has_passed_cards")
