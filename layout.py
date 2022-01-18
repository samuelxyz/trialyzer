import itertools
from typing import Iterable
import threading

import board
import fingermap
from nstroke import *

class Layout:

    loaded = dict() # dict of layouts

    def __init__(self, name: str, preprocess: bool = True) -> None:
        self.name = name
        self.keys = {} # dict[Pos, str]
        self.positions = {} # dict[str, Pos]
        self.fingers = {} # dict[str, Finger]
        self.coords = {} # dict[str, Coord]
        self.counts = {category: 0 for category in all_tristroke_categories}
        self.preprocessors = {}
        with open("layouts/" + name) as file:
            self.build_from_string(file.read())
        if preprocess:
            self.preprocessors["counts"] = threading.Thread(
                target=calculate_counts_wrapper, args=(self,), daemon=True)
            for name in self.preprocessors:
                self.preprocessors[name].start()

    def build_from_string(self, s: str):
        rows = []
        first_row = fingermap.Row.TOP
        first_col = 1
        self.fingermap = None
        self.board = None
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
        if not self.fingermap:
            self.fingermap = fingermap.get_fingermap("traditional")
        if not self.board:
            self.board = board.get_board("ansi")
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
        for other_name in Layout.loaded:
            other = Layout.loaded[other_name]
            if (other is not self
                and other.fingermap == self.fingermap 
                and other.board == self.board):
                # Will eventually need to account for alt fingering etc
                self.preprocessors["counts"] = other.preprocessors["counts"]
                self.counts = other.counts
                return

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

    def __repr__(self) -> str:
        first_row = min(pos.row for pos in self.keys)
        first_col = min(pos.col for pos in self.keys)
        last_row = max(pos.row for pos in self.keys)
        last_col = max(pos.col for pos in self.keys)
        rows = [
            f"fingermap: {self.fingermap.name}",
            f"board: {self.board.name}",
            f"first_pos: {fingermap.Row(first_row).name} {first_col}",
        ]
        for row in range(first_row, last_row+1):
            keys = []
            for col in range(first_col, last_col+1):
                try:
                    keys.append(self.keys[fingermap.Pos(row, col)])
                except KeyError:
                    keys.append("")
            rows.append(" ".join(keys))
        return "\n".join(rows)

    def to_ngram(self, nstroke: Nstroke):
        """Returns None if the Nstroke does not have a corresponding
        ngram in this layout. Otherwise, returns a tuple of key names
        based on the coordinates in the tristroke, disregarding the 
        fingers and any notes.
        """
        ngram = []
        try:
            for coord in nstroke.coords:
                pos = self.board.positions[coord]
                key = self.keys[pos]
                ngram.append(key)
        except KeyError:
            return None
        return tuple(ngram)

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

    def ngrams_with_any_of(self, keys: Iterable[str], n: int = 3):
        # this method should avoid generating duplicates probably maybe
        options = tuple(key for key in keys if key in self.positions)
        inverse = tuple(key for key in self.positions if key not in options)
        all = tuple(key for key in self.positions)
        for i in range(n):
            by_position = []
            for j in range(n):
                if j > i:
                    by_position.append(all)
                elif j < i:
                    by_position.append(inverse)
                else:
                    by_position.append(options)
            for ngram in itertools.product(*by_position):
                # print(ngram)
                # yield self.to_nstroke(ngram)
                yield ngram

    def swap(self, keys: Sequence[str]):
        self.to_nstroke.cache_clear()
        (self.keys[self.positions[keys[1]]], 
            self.keys[self.positions[keys[0]]]) = keys
        self.positions[keys[1]], self.positions[keys[0]] = (
            self.positions[keys[0]], self.positions[keys[1]])
        self.fingers[keys[1]], self.fingers[keys[0]] = (
            self.fingers[keys[0]], self.fingers[keys[1]])
        self.coords[keys[1]], self.coords[keys[0]] = (
            self.coords[keys[0]], self.coords[keys[1]])

def get_layout(name: str) -> Layout:
    if name not in Layout.loaded:
        Layout.loaded[name] = Layout(name)
    return Layout.loaded[name]

def calculate_counts_wrapper(*args, **kwargs):
    args[0].calculate_counts()

# for testing
if __name__ == "__main__":
    qwerty = get_layout("qwerty")
    n = 3
    keys = ("a", "b", "c")
    set_1 = {nstroke for nstroke in qwerty.ngrams_with_any_of(keys, n)}
    print(len(set_1))