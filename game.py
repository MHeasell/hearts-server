from redis import WatchError

from uuid import uuid4

from util import get_status_key, STATUS_IN_GAME, redis_key, hand_key

from keys import GAME_EVENTS_QUEUE_KEY

import json


class AccessDeniedError(Exception):
    pass


class GameStateError(Exception):
    def __init__(self, msg=""):
        self.message = msg


def create_game(redis, players):
    # we got four players, lets create the game
    game_id = str(uuid4())

    # update the players in redis
    with redis.pipeline() as pipe:

        # TODO: check that the players are still in queuing state
        # before putting them into the game

        # update player state to mark them as in this game
        for player in players:
            status_key = get_status_key(player)
            pipe.set(status_key, STATUS_IN_GAME)
            pipe.set(redis_key("player", player, "current_game"), game_id)

        # add the players to the game's player list
        pipe.rpush(redis_key("game", game_id, "players"), *players)

        # put an init event in the queue
        # so that a dealer will set up this game
        pipe.lpush(GAME_EVENTS_QUEUE_KEY, ",".join(["init", game_id]))

        pipe.execute()


def get_players(redis, game_id):
    """
    Fetches the list of players for the given game.
    :param redis: A Redis database connection.
    :param game_id: The ID of the game to get players for.
    :return: The list of players.
    If the game does not exist, the list will be empty.
    """
    return redis.lrange(redis_key("game", game_id, "players"), 0, -1)


def get_hand(redis, game_id, round_number, player_name):
    """
    Fetches the set of cards in the player's hand.
    :param redis: A Redis database connection.
    :param game_id: The ID of the game.
    :param round_number: The number of the round.
    :param player_name: The name of the player whose hand we should fetch.
    :return: A set instance containing the cards in the hand.
    """
    return redis.smembers(hand_key(game_id, round_number, player_name))


def is_in_hand(redis, game_id, round_number, player_name, card):
    return redis.sismember(hand_key(game_id, round_number, player_name), card)


def is_in_received_cards(redis, game_id, round_number, player_name, card):
    passed_cards_key = redis_key(
        "game",
        game_id,
        "rounds",
        round_number,
        "players",
        player_name,
        "passed_cards")
    return redis.sismember(passed_cards_key, card)


def get_pass_target(redis, game_id, round_number, player_name):
    # Find the index of this player.
    players = redis.lrange(redis_key("game", game_id, "players"), 0, -1)

    # this will raise ValueError if the player does not exist
    player_index = players.index(player_name)

    # Figure out the name of the player they should have passed to.
    # TODO: consider the round number when deciding who to pass to
    target_index = (player_index + 1) % 4
    target_name = players[target_index]

    target_passed_cards_key = redis_key(
        "game",
        game_id,
        "rounds",
        round_number,
        "players",
        target_name,
        "passed_cards")


def has_received_cards(redis, game_id, round_number, player_name):
    passed_cards_key = redis_key(
        "game",
        game_id,
        "rounds",
        round_number,
        "players",
        player_name,
        "passed_cards")
    return redis.scard(passed_cards_key) > 0


def get_passed_cards(redis, game_id, round_number, player_name):
    """
    Fetches the cards that this player was passed.
    Returns empty set if there are no cards yet.
    :param redis: A redis connection.
    :param game_id: The ID of the game.
    :param round_number: The round number.
    :param player_name: The name of the player.
    :return: The set of passed cards.

    """
    our_passed_cards_key = redis_key(
        "game",
        game_id,
        "rounds",
        round_number,
        "players",
        player_name,
        "passed_cards")

    return redis.smembers(our_passed_cards_key)


def pass_cards(redis, game_id, round_number, from_player, to_player, cards):
    with redis.pipeline() as pipe:
        while True:
            try:
                requester_hand_key = redis_key(
                    "game",
                    game_id,
                    "rounds",
                    round_number,
                    "players",
                    from_player,
                    "hand")

                target_passed_cards_key = redis_key(
                    "game",
                    game_id,
                    "rounds",
                    round_number,
                    "players",
                    to_player,
                    "passed_cards")

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
                    if not is_in_hand(pipe, game_id, round_number, from_player, c):
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


def play_card(redis, game_id, round_number, pile_number, player, card):
    pile_key = redis_key("game", game_id, "rounds", round_number, "piles", pile_number)

    with redis.pipeline() as pipe:
        while True:
            try:
                player_hand_key = hand_key(game_id, round_number, player)
                passed_cards_key = redis_key(
                    "game",
                    game_id,
                    "rounds",
                    round_number,
                    "players",
                    player,
                    "passed_cards"
                )

                pipe.watch(player_hand_key)
                pipe.watch(passed_cards_key)

                if not is_in_hand(pipe, game_id, round_number, player, card) \
                        and not is_in_received_cards(pipe, game_id, round_number, player, card):
                    err = "{0}'s hand does not contain card {1}."
                    raise GameStateError(err.format(player, card))

                blob = json.dumps({"player": player, "card": card})

                pipe.multi()
                pipe.srem(player_hand_key, card)
                pipe.srem(passed_cards_key, card)
                pipe.rpush(pile_key, blob)
                pipe.execute()

            except WatchError:
                continue