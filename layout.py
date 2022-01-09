import itertools
from typing import Iterable
import threading

import board
import fingermap
from nstroke import *

class Layout:

    loaded = {} # dict of layouts

    def __init__(self, name: str) -> None:
        self.name = name
        self.keys = {} # dict[Pos, str]
        self.positions = {} # dict[str, Pos]
        self.fingers = {} # dict[str, Finger]
        self.coords = {} # dict[str, Coord]
        self.counts = {category: 0 for category in all_tristroke_categories}
        self.preprocessors = {
            "counts": threading.Thread(
                target=calculate_counts_wrapper, args=(self,), daemon=True)
        }
        with open("layouts/" + name) as file:
            self.build_from_string(file.read())
        for name in self.preprocessors:
            self.preprocessors[name].start()

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
                    self.fingers[key] = self.fingermap.fingers[
                        self.positions[key]]
                    self.coords[key] = self.board.coords[
                        self.positions[key]]

    def calculate_counts(self):
        for tristroke in self.all_nstrokes(3):
            self.counts[tristroke_category(tristroke)] += 1
        for category in all_tristroke_categories:
            if not self.counts[category]:
                applicable = applicable_function(category)
                for instance in all_tristroke_categories:
                    if applicable(instance):
                        self.counts[category] += self.counts[instance]
    
    def __str__(self) -> str:
        return (self.name + " (" + self.fingermap.name + ", " 
            + self.board.name +  ")")

    @functools.cache
    def to_nstroke(self, ngram: Iterable[str], note: str = "", 
                     fingers: Iterable[fingermap.Finger] = ...) -> Nstroke:
        """Converts an ngram into an nstroke. Leave fingers blank
        to auto-calculate from the keymap. Since this uses functools.cache,
        give immutable arguments only.
        """
        
        if fingers == ...:
            fingers = (self.fingers[key] for key in ngram)
        return Nstroke(note, tuple(fingers),
                      tuple(self.coords[key] for key in ngram))

    def all_nstrokes(self, n: int = 3):
        ngrams = itertools.product(self.keys.values(), repeat=n)
        return (self.to_nstroke(ngram) for ngram in ngrams)

    def nstrokes_with_fingers(self, fingers: Iterable[fingermap.Finger]):
        options = []
        for finger in fingers:
            options.append((
                self.keys[pos] for pos in self.fingermap.cols[finger] 
                    if pos in self.keys))
        return (self.to_nstroke(item) for item in itertools.product(*options))

def get_layout(name: str) -> Layout:
    if name not in Layout.loaded:
        Layout.loaded[name] = Layout(name)
    return Layout.loaded[name]

def calculate_counts_wrapper(*args, **kwargs):
    args[0].calculate_counts()

# for testing
if __name__ == "__main__":
    qwerty = get_layout("qwerty")
    abc = qwerty.to_nstroke("abc")
    for item in qwerty.nstrokes_with_fingers(abc.fingers):
        print(item)