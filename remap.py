# Object to represent a superset of swaps, cycles, row/column swaps, etc

from typing import Container, Iterable, Sequence

from layout import Layout
from fingermap import Pos, Row

def cycle(keys: Sequence[str]):
    remap = Remap()
    for i in range(len(keys)):
        remap[keys[i]] = keys[i-1]
    return remap

swap = cycle

def set_swap(first: Sequence[str], second: Sequence[str]):
    remap = Remap()
    for a, b in zip(first, second):
        remap[a] = b
        remap[b] = a
    return remap

def row_swap(layout_: Layout, r1: Row, r2: Row, 
             pins: Container[str] = tuple()):
    remap = Remap()
    for pos, key in layout_.keys.items():
        if key not in pins and pos.row == r1:
            try:
                otherkey = layout_.keys[Pos(r2, pos.col)]
            except KeyError:
                continue
            if otherkey in pins:
                continue
            remap[key] = otherkey
            remap[otherkey] = key
    return remap

def col_swap(layout_: Layout, c1: int, c2: int,
             pins: Container[str] = tuple()):
    remap = Remap()
    for pos, key in layout_.keys.items():
        if key not in pins and pos.col == c1:
            try:
                otherkey = layout_.keys[Pos(pos.row, c2)]
            except KeyError:
                continue
            if otherkey in pins:
                continue
            remap[key] = otherkey
            remap[otherkey] = key
    return remap

class Remap(dict):
    
    def translate(self, ngram: Iterable[str]) -> tuple[str, ...]:
        return tuple(self.get(key, key) for key in ngram)

    def __str__(self) -> str:
        if not self:
            return "no-op"

        sequences = []
        for key, nextkey in self.items():
            added = False
            for sequence in sequences:
                if sequence[-1] == key:
                    added = True
                    if sequence[0] != nextkey:
                        sequence.append(nextkey)
                    continue
            if not added:
                sequences.append([key, nextkey])
        descriptions = []
        cycles = []
        swaps = []
        for sequence in sequences:
            if len(sequence) > 2:
                cycles.append(sequence)
            else:
                swaps.append(sequence)
        src, dest = zip(*swaps)
        descriptions.append(f"{' '.join(src)} <-> {' '.join(dest)}")
        for cycle_ in cycles:
            descriptions.append(f"{' '.join(cycle_)} cycle")
        
        return ", ".join(descriptions)

if __name__ == "__main__":
    import layout
    qwerty = layout.get_layout('qwerty')
    r = col_swap(qwerty, 2, 3)
    print(r)