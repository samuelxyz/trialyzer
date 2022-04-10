import random
from typing import Container

from fingermap import Pos, Row
from layout import Layout
import remap

class Constraintmap:

    loaded = {}

    def __init__(self, name: str) -> None:
        self.name = name
        self.caps = {} # type: dict[Pos, float]
        with open("constraintmaps/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s: str):
        rows = []
        first_row = Row.TOP
        first_col = 1
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
                    freq = float(token)
                    pos = Pos(r + first_row, c + first_col)
                    self.caps[pos] = freq

    def is_layout_legal(self, layout_: Layout, key_freqs: dict[str, float]):
        for key, pos in layout_.positions.items():
            if key_freqs[key] > self.caps.get(pos, 1.0):
                return False
        return True

    def is_remap_legal(self, layout_: Layout, key_freqs: dict[str, float],
                       remap: dict[str, str]):
        for key, dest in remap.items():
            try:
                if key_freqs[key] > self.caps.get(layout_.positions[dest], 1.0):
                    return False
            except KeyError:
                continue
        return True
    
    def random_legal_swap(self, layout_: Layout, 
                          key_freqs: dict[str, float],
                          pins: Container[str] = tuple()):
        destinations = False
        while not destinations:
            first_key = random.choice(
                tuple(k for k in layout_.positions if k not in pins))
            first_pos = layout_.positions[first_key]
            first_freq = key_freqs[first_key]
            first_cap = self.caps.get(first_pos, 1.0)
            destinations = tuple(key for key, pos in layout_.positions.items()
                if (key != first_key
                    and key not in pins
                    and first_freq < self.caps.get(pos, 1.0) 
                    and key_freqs[key] < first_cap
            ))
        return remap.swap((first_key, random.choice(destinations)))

def get_constraintmap(name: str) -> Constraintmap:
    if name not in Constraintmap.loaded:
        Constraintmap.loaded[name] = Constraintmap(name)
    return Constraintmap.loaded[name]