import itertools
import json
from typing import Iterable, Dict, Tuple, Sequence
import threading
import random
import functools

import board
import fingermap
from nstroke import (
    all_tristroke_categories, Nstroke, applicable_function, tristroke_category
)

class Layout:

    loaded = {} # type: Dict[str, Layout]

    def __init__(
            self, name: str, preprocess: bool = True, 
            repr_: str = "") -> None:
        """Pass in repr_ to build the layout directly from it. Otherwise, 
        the layout will be built from the file at layouts/<name>. Raises
        OSError if no repr is provided and no file is found."""
        self.name = name
        self.keys = {} # type: Dict[fingermap.Pos, str]
        self.positions = {} # type: Dict[str, fingermap.Pos]
        self.fingers = {} # type: Dict[str, fingermap.Finger]
        self.coords = {} # type: Dict[str, fingermap.Coord]
        self.counts = {category: 0 for category in all_tristroke_categories}
        self.preprocessors = {} # type: Dict[str, threading.Thread]
        if repr_:
            self.build_from_string(repr_)
        else:
            with open("layouts/" + name) as file:
                self.build_from_string(file.read())
        if preprocess:
            self.start_preprocessing()

    def build_from_string(self, s: str):
        rows = []
        first_row = fingermap.Row.TOP
        first_col = 1
        fingermap_defined = False
        board_defined = False
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
        if not fingermap_defined:
            self.fingermap = fingermap.get_fingermap("traditional")
        if not board_defined:
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
        for other in Layout.loaded.values():
            if (other is not self and self.has_same_tristrokes(other)):
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
    
    def has_same_tristrokes(self, other: "Layout"):
        return (
            self.fingermap == other.fingermap and
            self.board == other.board and
            set(self.coords.values()) == set(other.coords.values())
        )
    
    def start_preprocessing(self):
        self.preprocessors["counts"] = threading.Thread(
            target=_calculate_counts_wrapper, args=(self,), daemon=True)
        for name in self.preprocessors:
            self.preprocessors[name].start()
    
    def __str__(self) -> str:
        return (self.name + " (" + self.fingermap.name + ", " 
            + self.board.name +  ")")

    def __repr__(self) -> str:
        first_row = min(pos.row for pos in self.keys)
        first_col = min(pos.col for pos in self.keys)
        last_row = max(pos.row for pos in self.keys)
        last_col = max(pos.col for pos in self.keys)
        rows = []
        if self.fingermap.name != "traditional":
            rows.append(f"fingermap: {self.fingermap.name}")
        if self.board.name != "ansi":
            rows.append(f"board: {self.board.name}")
        if first_row != fingermap.Row.TOP.value or first_col != 1:
            rows.append(
                f"first_pos: {fingermap.Row(first_row).name} {first_col}")
        for row in range(first_row, last_row+1):
            keys = []
            for col in range(first_col, last_col+1):
                try:
                    keys.append(self.keys[fingermap.Pos(row, col)])
                except KeyError:
                    keys.append("")
            rows.append(" ".join(keys))
        return "\n".join(rows)

    @functools.cache
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
    def to_nstroke(self, ngram: Tuple[str, ...], note: str = "", 
                     fingers: Tuple[fingermap.Finger, ...] = ...):
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

    @functools.cache
    def nstrokes_with_fingers(self, fingers: Tuple[fingermap.Finger]):
        options = []
        for finger in fingers:
            options.append((
                self.keys[pos] for pos in self.fingermap.cols[finger] 
                    if pos in self.keys))
        return tuple(self.to_nstroke(item) 
            for item in itertools.product(*options))

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

    def shuffle(self, swaps: int = 100, pins: Iterable[str] = tuple()):
        keys = set(self.keys.values())
        for key in pins:
            keys.discard(key)
        random.seed()
        for _ in range(swaps):
            self.swap(random.sample(keys, k=2))

    def frequency_by_finger(self, lfreqs = ...):
        if lfreqs == ...:
            with open("data/shai.json") as file:
                corp_data = json.load(file)
            lfreqs = corp_data["letters"]
        fing_freqs = {finger: 0.0 for finger in list(fingermap.Finger)}
        for finger in self.fingermap.cols:
            for pos in self.fingermap.cols[finger]:
                try:
                    key = self.keys[pos]
                    lfreq = lfreqs[key]
                except KeyError:
                    continue
                fing_freqs[finger] += lfreq
        total_lfreq = sum(fing_freqs.values())
        if not total_lfreq:
            return {finger: 0.0 for finger in fing_freqs}
        for finger in fing_freqs:
            fing_freqs[finger] /= total_lfreq
        return fing_freqs

    def total_freq(self, trigram_freqs: dict):
        total = 0
        for trigram, freq in trigram_freqs.items():
            for key in trigram:
                if not key in self.positions:
                    continue
            total += freq
        return total

def get_layout(name: str) -> Layout:
    if name not in Layout.loaded:
        Layout.loaded[name] = Layout(name)
    return Layout.loaded[name]

def _calculate_counts_wrapper(*args: Layout):
    args[0].calculate_counts()

# for testing
if __name__ == "__main__":
    qwerty = get_layout("qwerty")
    n = 3
    keys = ("a", "b", "c")
    set_1 = {nstroke for nstroke in qwerty.ngrams_with_any_of(keys, n)}
    print(len(set_1))