from collections import defaultdict
import enum
#from collections import namedtuple
from typing import Dict, List, NamedTuple

class Row(enum.IntEnum):
    NUMBER = 0
    TOP = 1
    HOME = 2
    BOTTOM = 3
    THUMB = 4

# Pos = collections.namedtuple("Pos", ["row", "col"]) # integer row and col
class Pos(NamedTuple):
    row: Row
    col: int

class Finger(enum.IntEnum):
    LP = -5
    LR = -4
    LM = -3
    LI = -2
    LT = -1
    RT = 1
    RI = 2
    RM = 3
    RR = 4
    RP = 5
    UNKNOWN = 0

def unknown_finger(): # for picklability
    return Finger.UNKNOWN

class Fingermap:

    loaded = {} # dict of fingermaps

    def __init__(self, name: str) -> None:
        self.name = name
        self.fingers = defaultdict(unknown_finger) # type: Dict[Pos, Finger]
        self.cols: Dict[Finger, List[Pos]] = {finger: [] for finger in Finger}
        with open("fingermaps/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s: str):
        rows = [] # rows in the string which specify the layout
        first_row = Row.NUMBER
        first_col = 0
        for row in s.splitlines():
            # double spaces matter so not just .split()
            # also, allow comments at end with "//"
            tokens = row.split("//", 1)[0].split(" ")
            if tokens[0] == "first_pos:" and len(tokens) >= 3:
                try:
                    first_row = int(tokens[1])
                except ValueError:
                    first_row = Row[tokens[1]].value
                first_col = int(tokens[2])
            else:
                rows.append(tokens)
        for r, row in enumerate(rows):
            for c, token in enumerate(row):
                if token:
                    try:
                        finger = Finger(int(token))
                    except ValueError:
                        try:
                            finger = Finger[token]
                        except KeyError:
                            finger = Finger.UNKNOWN
                    pos = Pos(r + first_row, c + first_col)
                    self.fingers[pos] = finger
                    self.cols[finger].append(pos)

def get_fingermap(name: str) -> Fingermap:
    if name not in Fingermap.loaded:
        Fingermap.loaded[name] = Fingermap(name)
    return Fingermap.loaded[name]