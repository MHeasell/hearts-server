from uuid import uuid4
import json

from redis import WatchError

from hearts.util import redis_key
from hearts.keys import GAME_EVENTS_QUEUE_KEY


class AccessDeniedError(Exception):
    pass


class GameStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


class GameEventQueueService(object):

    def __init__(self, redis):
        self.redis = redis

    def raise_init_event(self, game_id):
        self.redis.rpush(GAME_EVENTS_QUEUE_KEY, ",".join(["init", game_id]))


def _players_key(game_id):
        return redis_key("game", game_id, "players")


class GameService(object):

    def __init__(self, redis):
        self.redis = redis

    def create_game(self, players):
        game_id = str(uuid4())
        self.redis.rpush(_players_key(game_id), *players)
        return game_id

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

    def get_pass_direction(self):
        dirs = ["left", "across", "right", "none"]
        index = (self.round_number - 1) % 4
        return dirs[index]

    def has_received_cards(self, player_name):
        if self.get_pass_direction() == "none":
            return True

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

    def pass_cards(self, from_player, to_player, cards):
        requester_hand_key = self._hand_key(from_player)
        target_passed_cards_key = self._received_cards_key(to_player)

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

                    if not pipe.sismember(player_hand_key, card) \
                            and not pipe.sismember(passed_cards_key, card):
                        err = "{0}'s hand does not contain card {1}."
                        raise GameStateError(err.format(player, card))

                    blob = json.dumps({"player": player, "card": card})

                    pipe.multi()
                    pipe.srem(player_hand_key, card)
                    pipe.srem(passed_cards_key, card)
                    pipe.rpush(pile_key, blob)
                    pipe.execute()

                    break

                except WatchError:
                    continue

    def get_pile(self, pile_number):
        key = self._pile_key(pile_number)
        return self.redis.lrange(key, 0, -1)

    def get_pile_card(self, pile_number, card_number):
        key = self._pile_key(pile_number)
        return self.redis.lindex(key, card_number - 1)

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