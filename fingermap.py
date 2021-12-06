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
    UNKNOWN = 10

class Fingermap:

    loaded = {} # dict of fingermaps
    
    @staticmethod
    def get(name):
        try:
            return Fingermap.loaded[name]
        except KeyError:
            Fingermap.loaded[name] = Fingermap(name)
            return Fingermap.loaded[name]

    def __init__(self, name) -> None:
        self.name = name
        self.fingers = {} # dict Pos -> Finger
        self.cols = [] # list of lists of Pos
        with open("fingermaps/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s):
        rows = []
        first_row = Row.NUMBER
        first_col = 0
        for row in s.split("\n"):
            tokens = row.split(" ")
            if tokens[0] == "first_pos:" and len(tokens) >= 3:
                try:
                    first_row = int(tokens[1])
                except ValueError:
                    first_row = Row[tokens[1]]
                first_col = int(tokens[2])
            else:
                rows.append(tokens)
        for r, row in enumerate(rows):
            for c, token in enumerate(row):
                if token:
                    try:
                        finger = int(token)
                    except ValueError:
                        try:
                            finger = Finger[token]
                        except KeyError:
                            finger = Finger.UNKNOWN
                    pos = Pos(r + first_row, c + first_col)
                    self.fingers[pos] = finger
                    self.cols[finger].append(pos)
    
    def load_fingermaps(self):
        pass
    
    def get_finger(self, pos):
        return self.fingers[pos]

    def get_column(self, finger):
        return self.cols[finger]

