from typing import NamedTuple

from fingermap import Pos, Row

# Coord = collections.namedtuple("Coord", ["x", "y"])
class Coord(NamedTuple):
    x: float
    y: float

class Board:
    
    loaded = {} # dict of boards

    def __init__(self, name: str) -> None:
        self.name = name
        self.positions = {} # type: dict[Coord, Pos]
        self.coords = {} # type: dict[Pos, Coord]
        self.default_keys = {} # type: dict[Pos, str]
        with open("boards/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s: str):
        for row in s.splitlines():
            # allow comments at end with "//"
            tokens = row.split("//", 1)[0].split()
            if not tokens:
                continue
            key_specified = (tokens[0] == "default_key:")
            if key_specified:
                tokens.pop(0)
            try:
                r = int(tokens[0])
            except ValueError:
                r = Row[tokens[0]].value
            c1 = int(tokens[1])
            if key_specified:
                self.default_keys[Pos(r, c1)] = tokens[2]
            else:
                x = float(tokens[2])
                y = float(tokens[3])
                if len(tokens) >= 5:
                    c2 = int(tokens[4])
                else:
                    c2 = c1
                for c in range(c1, c2 + 1):
                    pos = Pos(r, c)
                    coord = Coord(x, y)
                    self.positions[coord] = pos
                    self.coords[pos] = coord
                    x += 1

def get_board(name: str) -> Board:
    if name not in Board.loaded:
        Board.loaded[name] = Board(name)
    return Board.loaded[name]