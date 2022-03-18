from typing import NamedTuple

import fingermap

# Coord = collections.namedtuple("Coord", ["x", "y"])
class Coord(NamedTuple):
    x: float
    y: float

class Board:
    
    loaded = {} # dict of boards

    def __init__(self, name: str) -> None:
        self.name = name
        self.positions = {} # dict[Coord, Pos]
        self.coords = {} # dict[Pos, Coord]
        with open("boards/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s: str):
        for row in s.split("\n"):
            tokens = row.split()
            try:
                r = int(tokens[0])
            except ValueError:
                r = fingermap.Row[tokens[0]].value
            c1 = int(tokens[1])
            x = float(tokens[2])
            y = float(tokens[3])
            if len(tokens) >= 5:
                c2 = int(tokens[4])
            else:
                c2 = c1
            for c in range(c1, c2 + 1):
                pos = fingermap.Pos(r, c)
                coord = Coord(x, y)
                self.positions[coord] = pos
                self.coords[pos] = coord
                x += 1

def get_board(name: str) -> Board:
    if name not in Board.loaded:
        Board.loaded[name] = Board(name)
    return Board.loaded[name]