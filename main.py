from flask import Flask, jsonify, abort, request
from redis import StrictRedis, WatchError

from flask_cors import CORS

from uuid import uuid4

from util import *

from keys import QUEUE_KEY, QUEUE_CHANNEL_KEY

import json


app = Flask(__name__)
cors = CORS(app)

redis = StrictRedis(host='localhost', port=6379, db=0)


def find_requester_name():
    ticket = request.args.get("ticket", "")
    return redis.get(ticket_key(ticket))


def require_ticket_for(player):
    ticket_player = find_requester_name()
    if ticket_player != player:
        abort(403)


@app.route("/queue", methods=["POST"])
def queue():
    name = request.form["name"]
    ticket = str(uuid4())

    status_key = get_status_key(name)

    with redis.pipeline() as pipe:
        while 1:
            try:
                pipe.watch(status_key)
                status = pipe.get(status_key)
                if status == STATUS_IN_GAME:
                    print "player " + name + " is currently in a game"
                    abort(409)

                if status == STATUS_QUEUING:
                    print "player " + name + " is currently queuing"
                    abort(409)

                pipe.multi()
                pipe.set(ticket_key(ticket), name)
                pipe.lpush(QUEUE_KEY, name)
                pipe.set(status_key, STATUS_QUEUING)
                pipe.publish(QUEUE_CHANNEL_KEY, "player added")
                pipe.execute()
                return jsonify(ticket=ticket)
            except WatchError:
                continue


@app.route("/queue/<player>")
def show_queue_status(player):
    require_ticket_for(player)

    status = redis.get(get_status_key(player))
    if status == STATUS_QUEUING:
        return jsonify(matched=False)
    elif status == STATUS_IN_GAME:
        game = redis.get(redis_key("player", player, "current_game"))
        return jsonify(matched=True, link="/game/" + game)
    else:
        abort(404)


@app.route("/game/<game>/players")
def show_players(game):
    players = redis.lrange(redis_key("game", game, "players"), 0, -1)
    if players is None:
        abort(404)

    return jsonify(players=players)


@app.route("/game/<game>/rounds/<int:round_number>/players/<player>/hand")
def show_hand(game, round_number, player):
    require_ticket_for(player)

    hand = redis.smembers(hand_key(game, round_number, player))
    if hand is None or len(hand) == 0:
        abort(404)

    return jsonify(cards=list(hand))


@app.route("/game/<game>/rounds/<int:round_number>/players/<player>/passed_cards",
           methods=["GET", "POST"])
def passed_cards(game, round_number, player):
    if request.method == "GET":
        require_ticket_for(player)

        # figure out who this person should have passed to
        players = redis.lrange(redis_key("game", game, "players"), 0, -1)
        try:
            player_index = players.index(player)
        except ValueError:
            abort(403)
            return  # won't be reached, but needed to suppress IDE warning

        # TODO: consider the round number when deciding who to pass to
        target_index = (player_index + 1) % 4
        target = players[target_index]

        target_passed_cards_key = redis_key(
            "game",
            game,
            "rounds",
            round_number,
            "players",
            target,
            "passed_cards")

        # forbid access if their target doesn't have their cards yet
        if redis.scard(target_passed_cards_key) == 0:
            abort(403)

        our_passed_cards_key = redis_key(
            "game",
            game,
            "rounds",
            round_number,
            "players",
            player,
            "passed_cards")

        cards = redis.smembers(our_passed_cards_key)

        if cards is None or len(cards) == 0:
            abort(404)

        return jsonify(cards=list(cards))

    elif request.method == "POST":
        # figure out the player performing the request
        requester = find_requester_name()

        # figure out the index of both the requester
        # and the target player
        players = redis.lrange(redis_key("game", game, "players"), 0, -1)
        try:
            requester_index = players.index(requester)
            player_index = players.index(player)
        except ValueError:
            abort(403)
            return  # won't be reached, but needed to suppress IDE warning

        # figure out whether the requester is allowed to pass
        # to this player
        # TODO: consider round number when checking this
        allowed_index = (requester_index + 1) % 4
        if allowed_index != player_index:
            abort(403)

        # get the cards
        card1 = request.form["card1"]
        card2 = request.form["card2"]
        card3 = request.form["card3"]

        # try to transfer the cards
        with redis.pipeline() as pipe:
            while True:
                try:
                    requester_hand_key = redis_key(
                        "game",
                        game,
                        "rounds",
                        round_number,
                        "players",
                        requester,
                        "hand")

                    target_passed_cards_key = redis_key(
                        "game",
                        game,
                        "rounds",
                        round_number,
                        "players",
                        player,
                        "passed_cards")

                    # Make sure the cards don't change while we're doing this
                    pipe.watch(requester_hand_key)
                    pipe.watch(target_passed_cards_key)

                    # check that the target player has not already
                    # been given cards
                    if pipe.scard(target_passed_cards_key) != 0:
                        abort(409)

                    # check that the cards are in the requester's hand
                    for c in card1, card2, card3:
                        if not pipe.sismember(requester_hand_key, c):
                            abort(409)

                    pipe.multi()
                    # remove the cards from the requester's hand
                    pipe.srem(requester_hand_key, card1, card2, card3)

                    # add the cards to the target's passed cards collection
                    pipe.sadd(target_passed_cards_key, card1, card2, card3)
                    pipe.execute()

                    break

                except WatchError:
                    continue

        return jsonify(success=True)


@app.route("/game/<game>/rounds/<int:round_number>/piles/<int:pile_number>", methods=["GET", "POST"])
def show_pile(game, round_number, pile_number):

    pile_key = redis_key("game", game, "rounds", round_number, "piles", pile_number)

    if request.method == "GET":
        cards = redis.lrange(pile_key, 0, -1)
        cards = map(lambda x: json.loads(x), cards)

        return jsonify(cards=cards)

    elif request.method == "POST":
        player = request.form["player"]
        card = request.form["card"]

        require_ticket_for(player)

        # TODO: check that this player is allowed to play now.
        # i.e. it is their turn to play.
        # And also that the round/pile exists and stuff.

        # TODO: also actually check the game rules
        # to make sure that the move is legal!

        with redis.pipeline() as pipe:
            while True:
                try:
                    player_hand_key = hand_key(game, round_number, player)
                    passed_cards_key = redis_key(
                        "game",
                        game,
                        "rounds",
                        round_number,
                        "players",
                        player,
                        "passed_cards"
                    )

                    pipe.watch(player_hand_key)
                    pipe.watch(passed_cards_key)
                    hand = pipe.smembers(player_hand_key)
                    received_cards = pipe.smembers(passed_cards_key)

                    # check that the card is in their hand
                    if card not in hand and card not in received_cards:
                        abort(409)

                    blob = json.dumps({"player": player, "card": card})

                    pipe.multi()
                    pipe.srem(player_hand_key, card)
                    pipe.srem(passed_cards_key, card)
                    pipe.rpush(pile_key, blob)
                    pipe.execute()

                    return jsonify(success=True)
                except WatchError:
                    continue


@app.route("/game/<game>/rounds/<int:round_number>/piles/<int:pile_number>/<int:card_number>")
def show_pile_card(game, round_number, pile_number, card_number):
    pile_key = redis_key("game", game, "rounds", round_number, "piles", pile_number)

    card_json = redis.lindex(pile_key, card_number - 1)
    if card_json is None:
        abort(404)

    card_data = json.loads(card_json)

    return jsonify(**card_data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
