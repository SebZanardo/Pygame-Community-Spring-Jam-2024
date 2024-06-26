from enum import Enum, auto


class InputState(Enum):
    PRESSED = auto()
    HELD = auto()
    RELEASED = auto()


class MouseButton(Enum):
    LEFT = 0
    MIDDLE = 1
    RIGHT = 2


class Action(Enum):
    HOLD = auto()
    RESTART = auto()
    CENTRE = auto()
    MUTE = auto()
