import itertools
import json
import os
from typing import Collection, Iterable, Dict, Tuple, Callable
import threading
import random
import functools
import contextlib

import board
import fingermap
import corpus
import remap
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
        FileNotFoundError if no repr is provided and no file is found."""
        self.name = name
        self.keys = {} # type: Dict[fingermap.Pos, str]
        self.positions = {} # type: Dict[str, fingermap.Pos]
        self.fingers = {} # type: Dict[str, fingermap.Finger]
        self.coords = {} # type: Dict[str, board.Coord]
        self.counts = {category: 0 for category in all_tristroke_categories}
        self.preprocessors = {} # type: Dict[str, threading.Thread]
        self.nstroke_cache = {} # type: Dict[Tuple[str, ...], Nstroke]
        self.special_replacements = {} # type: Dict[str, Tuple[str,...]]
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
        self.repeat_key = ""
        for row in s.splitlines():
            tokens = row.split("//", 1)[0].split(" ")
            if tokens[0] == "fingermap:":
                if len(tokens) >= 2:
                    self.fingermap = fingermap.get_fingermap(tokens[1])
                    fingermap_defined = True
            elif tokens[0] == "board:":
                if len(tokens) >= 2:
                    self.board = board.get_board(tokens[1])
                    board_defined = True
            elif tokens[0] == "first_pos:":
                if len(tokens) >= 3:
                    try:
                        first_row = int(tokens[1])
                    except ValueError:
                        first_row = fingermap.Row[tokens[1]]
                    first_col = int(tokens[2])
            elif tokens[0] == "special:":
                if len(tokens) >= 3:
                    self.special_replacements[tokens[1]] = tuple(tokens[2:])
            elif tokens[0] == "repeat_key:":
                if len(tokens) >= 2:
                    self.repeat_key = tokens[1]
            elif len("".join(tokens)):
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
        for pos, key in self.board.default_keys.items():
            if pos not in self.keys and key not in self.positions:
                self.keys[pos] = key
                self.positions[key] = pos
                self.fingers[key] = self.fingermap.fingers[
                    self.positions[key]]
                self.coords[key] = self.board.coords[
                    self.positions[key]]

    def calculate_category_counts(self):
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
        reprkeys = self.get_board_keys()[1]

        first_row = min(pos.row for pos in reprkeys)
        first_col = min(pos.col for pos in reprkeys)
        last_row = max(pos.row for pos in reprkeys)
        last_col = max(pos.col for pos in reprkeys)
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
                    keys.append(reprkeys[fingermap.Pos(row, col)])
                except KeyError:
                    keys.append("")
            rows.append(" ".join(keys))
        if bool(self.repeat_key):
            rows.append(f"repeat_key: {self.repeat_key}")
        for k, v in self.special_replacements.items():
            rows.append(f"special: {k} {' '.join(v)}")
        return "\n".join(rows)

    def get_board_keys(self):
        """Returns board_keys, non_board_keys as dicts[pos, key] that 
        are/are not from the default keys of the board.
        """
        board_keys = {}
        non_board_keys = {}
        for pos, key in self.keys.items():
            if (pos, key) in self.board.default_keys.items():
                board_keys[pos] = key
            else:
                non_board_keys[pos] = key
        return board_keys, non_board_keys

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

    #@functools.cache
    def to_nstroke(self, ngram: Tuple[str, ...], note: str = "", 
                     fingers: Tuple[fingermap.Finger, ...] = ...,
                     overwrite_cache: bool = False):
        """Converts an ngram into an nstroke. Leave fingers blank
        to auto-calculate from the keymap. Since this uses functools.cache,
        give immutable arguments only.

        Raises KeyError if a key is not found in the layout.
        """
        is_pure_ngram = (note == "" and fingers == ...)
        if not overwrite_cache:
            try:
                if is_pure_ngram:
                    return self.nstroke_cache[ngram]
                else:
                    args = (ngram, note, fingers)
                    return self.nstroke_cache[args]
            except KeyError:
                pass
        
        if fingers == ...:
            fingers = (self.fingers[key] for key in ngram)
        result = Nstroke(note, tuple(fingers),
                      tuple(self.coords[key] for key in ngram))
                      
        if is_pure_ngram:
            self.nstroke_cache[ngram] = result
        else:
            args = (ngram, note, fingers)
            self.nstroke_cache[args] = result
        return result

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

    def ngrams_with_any_of(self, keys: Iterable[str], n: int = 3,
            exclude_keys: Collection[str] = ()):
        """Any key in exclude_keys will be excluded from the result."""
        # this method should avoid generating duplicates probably maybe
        options = tuple(key for key in keys 
            if key in self.positions and key not in exclude_keys)
        inverse = tuple(key for key in self.positions 
            if key not in options and key not in exclude_keys)
        all = tuple(key for key in self.positions if key not in exclude_keys)
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

    def remap(self, remap: dict[str, str], refresh_cache: bool = True):
        k = {self.positions[dest]: key for key, dest in remap.items()}
        p = {key: self.positions[dest] for key, dest in remap.items()}
        f = {key: self.fingers[dest] for key, dest in remap.items()}
        c = {key: self.coords[dest] for key, dest in remap.items()}
        self.keys.update(k)
        self.positions.update(p)
        self.fingers.update(f)
        self.coords.update(c)
        self.nstrokes_with_fingers.cache_clear()
        # self.to_nstroke.cache_clear()
        if refresh_cache:
            for ngram in self.ngrams_with_any_of(remap):
                self.to_nstroke(ngram, overwrite_cache=True)

    def shuffle(self, swaps: int = 100, pins: Iterable[str] = tuple()):
        keys = set(self.keys.values())
        for key in pins:
            keys.discard(key)
        random.seed()
        for _ in range(swaps):
            self.remap(remap.cycle(*random.sample(keys, k=2)), False)
        self.nstroke_cache.clear()

    def constrained_shuffle(self, shuffle_source: Callable, swaps: int = 100):
        for _ in range(swaps):
            self.remap(shuffle_source(), False)
        self.nstroke_cache.clear()

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

    def total_trigram_count(self, corpus_settings: dict):
        total = 0
        trigram_counts = self.get_corpus(corpus_settings).trigram_counts
        for trigram, count in trigram_counts.items():
            for key in trigram:
                if not key in self.positions:
                    continue
            total += count
        return total

    def get_corpus(self, settings: dict):
        return corpus.get_corpus(
            settings["filename"],
            "space" if ("space" in self.keys.values()) and settings["space_key"]
                else settings["space_key"],
            "shift" if ("shift" in self.keys.values()) and settings["shift_key"]
                else settings["shift_key"],
            settings["shift_policy"],
            self.special_replacements,
            self.repeat_key,
            settings["precision"]
        )

    def is_saved(self) -> bool:
        return os.path.exists(f"layouts/{self.name}")
        # check repr? I don't think there should ever be a situation 
        # where self differs from what's in the file
        # So this should be fine for now

def get_layout(name: str) -> Layout:
    if name not in Layout.loaded:
        Layout.loaded[name] = Layout(name)
    return Layout.loaded[name]

def _calculate_counts_wrapper(*args: Layout):
    args[0].calculate_category_counts()

@contextlib.contextmanager
def make_picklable(layout_: Layout):
    preprocessors = layout_.preprocessors
    layout_.preprocessors = {}
    try:
        yield layout_
    finally:
        layout_.preprocessors = preprocessors
    

# for testing
if __name__ == "__main__":
    qwerty = get_layout("qwerty")
    n = 3
    keys = ("a", "b", "c")
    set_1 = {nstroke for nstroke in qwerty.ngrams_with_any_of(keys, n)}
    print(len(set_1))