import json

from redis import WatchError

import hearts.util as u
from hearts.util import redis_key, retry_transaction
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
        self.game_svc = GameService(self.redis)

    def create_round(self, hands):
        game_key = _game_key(self.game_id)
        prev_round_id = int(self.redis.hget(game_key, "current_round"))

        round_id = prev_round_id + 1

        received_key = self._received_key(round_id)
        passed_key = self._passed_key(round_id)

        round_data = {
            "id": round_id,
            "state": "passing",
            "current_pile": 0
        }

        with self.redis.pipeline() as pipe:
            # set everyone's hand
            for player, hand in hands.iteritems():
                pipe.sadd(self._hand_key(round_id, player), *hand)

            pipe.hmset(self._round_key(round_id), round_data)
            pipe.hset(game_key, "current_round", round_id)

            for player in hands.iterkeys():
                pipe.hset(received_key, player, 0)
                pipe.hset(passed_key, player, 0)

            pipe.execute()

        return round_id

    def get_round(self, round_id):
        data = self.redis.hgetall(self._round_key(round_id))

        data["id"] = int(data["id"])
        data["current_pile"] = int(data["current_pile"])

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
            if v == "0":
                return False
        return True

    def pass_cards(self, round_id, from_player, to_player, cards):
        requester_hand_key = self._hand_key(round_id, from_player)
        target_passed_cards_key = self._received_cards_key(round_id, to_player)

        has_passed_key = self._passed_key(round_id)
        has_received_key = self._received_key(round_id)

        players = self.redis.lrange(_players_key(self.game_id), 0, -1)
        players = map(int, players)

        from_index = players.index(from_player)
        to_index = players.index(to_player)
        expected_to_index = (from_index + u.get_pass_offset(u.get_pass_direction(round_id))) % 4

        if to_index != expected_to_index:
            raise AccessDeniedError()

        def transact(pipe):
            # Make sure the cards don't change while we're doing this
            pipe.watch(requester_hand_key)
            pipe.watch(target_passed_cards_key)

            # check that the target player has not already
            # been given cards
            if pipe.hget(has_received_key, to_player) == "1":
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

        retry_transaction(self.redis, transact)

        if self.have_all_received_cards(round_id):
            self._on_finish_passing(round_id)

    def _on_finish_passing(self, round_id):

        with self.redis.pipeline() as pipe:
            round_key = self._round_key(round_id)
            pipe.hset(round_key, "state", "passing-completed")
            pipe.execute()

        players = self.game_svc.get_game(self.game_id)["players"]

        start_player = None
        for player in map(lambda x: x["id"], players):
            hand = self.get_hand(round_id, player)
            received_cards = self.get_passed_cards(round_id, player)
            if "c2" in hand or "c2" in received_cards:
                start_player = player
                break

        assert start_player is not None

        self.create_pile(round_id, start_player)

        with self.redis.pipeline() as pipe:
            round_key = self._round_key(round_id)
            pipe.hset(round_key, "state", "playing")
            pipe.execute()

    def create_pile(self, round_id, starting_player):
        round_data = self.get_round(round_id)

        pile_id = round_data["current_pile"] + 1
        data = {
            "id": pile_id,
            "state": "open",
            "current_player": starting_player,
        }

        self.redis.hmset(self._pile_data_key(round_id, pile_id), data)
        self.redis.hset(self._round_key(round_id), "current_pile", pile_id)

        return pile_id

    def play_card(self, round_id, pile_number, player, card):
        round_data = self.get_round(round_id)

        if round_data["state"] != "playing":
            raise GameStateError("round is not in the playing state")

        if round_data["current_pile"] != pile_number:
            raise GameStateError("this trick is not currently in play")

        cur_player = self.redis.hget(self._pile_data_key(round_id, pile_number), "current_player")
        cur_player = int(cur_player)
        if cur_player != player:
            raise GameStateError("it is not your turn")

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

    def get_pile(self, round_id, pile_number):
        key = self._pile_key(round_id, pile_number)
        data = self.redis.lrange(key, 0, -1)
        data = map(json.loads, data)
        return data

    def get_pile_card(self, round_id, pile_number, card_number):
        key = self._pile_key(round_id, pile_number)
        data = self.redis.lindex(key, card_number - 1)
        return json.loads(data)

    def get_all_piles(self, round_id):
        cur_pile = self.get_round(round_id)["current_pile"]
        with self.redis.pipeline() as pipe:
            for i in xrange(1, cur_pile + 1):
                pipe.lrange(self._pile_key(round_id, i), 0, -1)

            piles = pipe.execute()

        return map(lambda x: map(json.loads, x), piles)

    def _round_key(self, round_id):
        return redis_key("game", self.game_id, "rounds", round_id)

    def _pile_data_key(self, round_id, pile_id):
        return redis_key(
            "game",
            self.game_id,
            "rounds",
            round_id,
            "piles",
            pile_id,
            "data")

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
