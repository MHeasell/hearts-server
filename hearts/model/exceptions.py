class GameStateError(Exception):
    pass


class RoundNotInProgressError(GameStateError):
    pass


class IncorrectPassPlayerError(GameStateError):
    pass


class CardsNotInHandError(GameStateError):
    pass


class CardsAlreadyPassedError(GameStateError):
    pass


class PlayersYetToPassError(GameStateError):
    pass


class PassingNotInProgressError(GameStateError):
    pass


class InvalidMoveError(GameStateError):
    pass


class InvalidHandError(GameStateError):
    pass


class GameAlreadyStartedError(GameStateError):
    pass
