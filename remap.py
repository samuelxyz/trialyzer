# Object to represent a superset of swaps, cycles, row/column swaps, etc

from typing import Iterable, Sequence

from layout import Layout
from fingermap import Pos, Row

def cycle(keys: Sequence[str]):
    remap = Remap()
    for i in range(len(keys)):
        remap[keys[i]] = remap[keys[i-1]]
    return remap

swap = cycle

def set_swap(first: Sequence[str], second: Sequence[str]):
    remap = Remap()
    for a, b in zip(first, second):
        remap[a] = b
        remap[b] = a
    return remap

def row_swap(layout_: Layout, r1: Row, r2: Row):
    remap = Remap()
    for pos, key in layout_.keys.items():
        if pos.row == r1:
            try:
                otherkey = layout_.keys[Pos(r2, pos.col)]
            except KeyError:
                continue
            remap[key] = otherkey
            remap[otherkey] = key
    return remap

def col_swap(layout_: Layout, c1: int, c2: int):
    remap = Remap()
    for pos, key in layout_.keys.items():
        if pos.col == c1:
            try:
                otherkey = layout_.keys[Pos(pos.row, c2)]
            except KeyError:
                continue
            remap[key] = otherkey
            remap[otherkey] = key
    return remap
                

class Remap(dict):
    
    def equivalent_ngram(self, ngram: Iterable[str]) -> tuple[str, ...]:
        return tuple(self.get(key, key) for key in ngram)