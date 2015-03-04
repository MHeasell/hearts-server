import json

from redis import WatchError

from hearts.util import redis_key
from hearts.keys import GAME_EVENTS_QUEUE_KEY

import time


class AccessDeniedError(Exception):
    pass


class GameStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


class GameNotFoundError(Exception):
    pass


class RoundNotFoundError(Exception):
    pass


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


def _game_key(game_id):
    return redis_key("game", game_id)


def _players_key(game_id):
        return redis_key("game", game_id, "players")


def _scores_key(game_id):
    return redis_key("game", game_id, "scores")


def _events_key(game_id):
    return redis_key("game", game_id, "events")


def _last_event_key(game_id):
    return redis_key("game", game_id, "last_event")


def _push_event(pipe, game_id, event_type, **event_keys):
    timestamp = time.time()
    event_keys["type"] = event_type
    event_keys["timestamp"] = timestamp
    event_json = json.dumps(event_keys)

    key = _events_key(game_id)
    pipe.zadd(key, timestamp, event_json)
    pipe.set(_last_event_key(game_id), timestamp)


class GameService(object):

    def __init__(self, redis):
        self.redis = redis

    def create_game(self, players):

        with self.redis.pipeline() as pipe:
            pipe.watch("next_game_id")

            game_id = int(pipe.get("next_game_id") or "1")

            game_data = {"id": game_id, "current_round": 0}

            score_data = dict(zip(players, [0] * len(players)))

            pipe.multi()
            pipe.hmset(_game_key(game_id), game_data)
            pipe.hmset(_scores_key(game_id), score_data)
            pipe.rpush(_players_key(game_id), *players)
            pipe.set("next_game_id", game_id + 1)
            pipe.execute()

            return game_id

    def get_game(self, game_id):
        key = _game_key(game_id)
        scores_key = _scores_key(game_id)

        with self.redis.pipeline() as pipe:
            pipe.hgetall(key)
            pipe.lrange(_players_key(game_id), 0, -1)
            pipe.hgetall(scores_key)
            data, players, scores = pipe.execute()

        if data is None:
            return None

        data["id"] = int(data["id"])
        data["current_round"] = int(data["current_round"])
        data["players"] = [{"id": int(p), "score": int(scores[p])} for p in players]

        return data

    def set_current_round(self, game_id, round_number):
        key = _game_key(game_id)

        if not self.redis.exists(key):
            raise GameNotFoundError()

        self.redis.hset(key, "current_round", round_number)

    def get_round_service(self, game_id):
        return GameRoundService(self.redis, game_id)

    def add_to_scores(self, game_id, score_dict):
        players = score_dict.keys()
        with self.redis.pipeline() as pipe:
            key = _scores_key(game_id)
            for player in players:
                pipe.hincrby(key, player, score_dict[player])
            new_scores = pipe.execute()

        return dict(zip(players, map(int, new_scores)))

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
    def __init__(self, redis, game_id):
        self.redis = redis
        self.game_id = game_id

    def create_round(self, hands):
        game_key = _game_key(self.game_id)
        prev_round_id = int(self.redis.hget(game_key, "current_round"))

        round_id = prev_round_id + 1

        round_data = {
            "id": round_id,
            "state": "passing"
        }

        with self.redis.pipeline() as pipe:
            # set everyone's hand
            for player, hand in hands.iteritems():
                pipe.sadd(self._hand_key(round_id, player), *hand)

            pipe.hmset(self._round_key(round_id), round_data)
            pipe.hset(game_key, "current_round", round_id)

            pipe.execute()

        return round_id

    def get_round(self, round_id):
        data = self.redis.hgetall(self._round_key(round_id))

        data["id"] = int(data["id"])

        return data

    def get_hand(self, round_id, player_name):
        """
        Fetches the set of cards in the player's hand.
        :param round_id: The round we should fetch a hand from.
        :param player_name: The name of the player whose hand we should fetch.
        :return: A set instance containing the cards in the hand.
        """
        if not self.redis.exists(self._round_key(round_id)):
            raise RoundNotFoundError()

        key = self._hand_key(round_id, player_name)
        return self.redis.smembers(key)

    def get_passed_cards(self, round_id, player_name):
        """
        Fetches the cards that this player was passed.
        Returns empty set if there are no cards yet.
        :param round_id: The round to fetch from.
        :param player_name: The name of the player.
        :return: The set of passed cards.
        """
        round_key = self._round_key(round_id)
        if self.redis.hget(round_key, "state") == "passing":
            raise AccessDeniedError()

        key = self._received_cards_key(round_id, player_name)
        return self.redis.smembers(key)

    def have_all_received_cards(self, round_id):
        data = self.redis.hgetall(self._received_key(round_id))
        for v in data.values():
            if int(v) == 0:
                return False
        return True

    def pass_cards(self, round_id, from_player, to_player, cards):
        requester_hand_key = self._hand_key(round_id, from_player)
        target_passed_cards_key = self._received_cards_key(round_id, to_player)

        has_passed_key = self._passed_key(round_id)
        has_received_key = self._received_key(round_id)

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
                    pipe.hset(has_passed_key, from_player, 1)
                    pipe.hset(has_received_key, to_player, 1)

                    pipe.execute()

                    break

                except WatchError:
                    continue

        if self.have_all_received_cards(round_id):
            self.redis.hset(self._round_key(round_id), "state", "playing")

    def play_card(self, round_id, pile_number, player, card):
        round_data = self.get_round(round_id)

        if round_data["state"] != "playing":
            raise GameStateError("round is not in the playing state")

        pile_key = self._pile_key(round_id, pile_number)
        player_hand_key = self._hand_key(round_id, player)
        passed_cards_key = self._received_cards_key(round_id, player)

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

    def _round_key(self, round_id):
        return redis_key("game", self.game_id, "rounds", round_id)

    def _pile_key(self, round_id, pile_number):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            round_id,
            "piles",
            pile_number)

    def _hand_key(self, round_id, player):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            round_id,
            "players",
            player,
            "hand")

    def _received_cards_key(self, round_id, player):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            round_id,
            "players",
            player,
            "passed_cards")

    def _received_key(self, round_id):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            round_id,
            "has_received_cards")

    def _passed_key(self, round_id):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            round_id,
            "has_passed_cards")
