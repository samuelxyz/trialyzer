from collections import namedtuple
from typing import Iterable

import board
import fingermap

Tristroke = namedtuple("Tristroke", "note fingers coords")

class Layout:

    loaded = {} # dict of layouts

    def __init__(self, name: str) -> None:
        self.name = name
        self.keys = {} # dict[Pos, str]
        self.positions = {} # dict[str, Pos]
        with open("layouts/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s: str):
        rows = []
        first_row = fingermap.Row.TOP
        first_col = 1
        for row in s.split("\n"):
            tokens = row.split(" ")
            if tokens[0] == "fingermap:" and len(tokens) >= 2:
                self.fingermap = fingermap.get_fingermap(tokens[1])
            elif tokens[0] == "board:" and len(tokens) >= 2:
                self.board = board.get_board(tokens[1])
            elif tokens[0] == "first_pos:" and len(tokens) >= 3:
                try:
                    first_row = int(tokens[1])
                except ValueError:
                    first_row = fingermap.Row[tokens[1]]
                first_col = int(tokens[2])
            else:
                rows.append(tokens)
        for r, row in enumerate(rows):
            for c, key in enumerate(row):
                if key:
                    pos = fingermap.Pos(first_row + r, first_col + c)
                    self.keys[pos] = key
                    self.positions[key] = pos

    def __str__(self) -> str:
        return (self.name + " (" + self.fingermap.name + ", " 
            + self.board.name +  ")")

    def finger(self, keyname: str) -> fingermap.Finger:
        return self.fingermap.fingers[self.positions[keyname]]

    def coord(self, keyname: str) -> board.Coord:
        return self.board.coords[self.positions[keyname]]

    def to_tristroke(self, trigram: Iterable[str], note: str = "", 
                     fingers: Iterable[fingermap.Finger] = ...) -> Tristroke:
        """Converts a trigram into a tristroke. Leave fingers blank
        to auto-calculate from the keymap.
        """
        
        if fingers == ...:
            fingers = (self.finger(char) for char in trigram)
        return Tristroke(note, tuple(fingers),
                      tuple(self.coord(char) for char in trigram))

def get_layout(name: str) -> Layout:
    if name not in Layout.loaded:
        Layout.loaded[name] = Layout(name)
    return Layout.loaded[name]

# for testing
if __name__ == "__main__":
    qwerty = get_layout("qwerty")
    print(qwerty.start_writable_row(qwerty.to_tristroke("abc")))