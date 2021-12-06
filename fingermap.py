import enum
from collections import namedtuple

Pos = namedtuple("Pos", ["row", "col"])

class Row(enum.IntEnum):
    NUMBER = 0
    TOP = 1
    HOME = 2
    BOTTOM = 3
    THUMB = 4

class Finger(enum.Enum):
    UNKNOWN = -1
    LP = 0
    LR = 1
    LM = 2
    LI = 3
    LT = 4
    RT = 5
    RI = 6
    RM = 7
    RR = 8
    RP = 9

class Fingermap:

    name = ""
    fingers = {}

    def __init__(self, name) -> None:
        self.name = name
        with open("fingermaps/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s):
        pass

    def get_finger(self, pos):
        pass