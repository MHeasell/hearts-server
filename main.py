from flask import Flask, jsonify, abort, request
from redis import StrictRedis, WatchError

from flask_cors import CORS

from uuid import uuid4

from util import *

from keys import QUEUE_KEY, QUEUE_CHANNEL_KEY


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


@app.route("/game/<game>/rounds/<round_number>/players/<player>/hand")
def show_hand(game, round_number, player):
    require_ticket_for(player)

    hand = redis.smembers(hand_key(game, round_number, player))
    if hand is None:
        abort(404)

    return jsonify(cards=list(hand))


@app.route("/game/<game>/rounds/<round_number>/players/<player>/passed_cards",
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

        cards = redis.lrange(our_passed_cards_key, 0, -1)

        if cards is None:
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
