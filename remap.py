# Object to represent a superset of swaps, cycles, row/column swaps, etc
# Remaps can be composed with each other using the + operator,
# and reversed using the - operator. Subtraction is also implemented but
# I have no clue when you would ever use that.

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

def layout_diff(initial: Layout, target: Layout):
    """Ignores fingermaps. Skips keys that are present on one layout 
    but not the other.
    """
    remap = Remap()
    for ipos, src in initial.keys.items():
        try:
            if src in remap:
                continue
            tpos = target.positions[src]
            if ipos == tpos:
                continue
            dest = initial.keys[tpos]
            first = src
            while dest != first:
                remap[src] = dest
                src = dest
                dest = initial.keys[target.positions[src]]
        except KeyError:
            continue
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
        if swaps:
            src, dest = zip(*swaps)
            descriptions.append(f"{' '.join(src)} <-> {' '.join(dest)}")
        for cycle_ in cycles:
            descriptions.append(f"{' '.join(cycle_)} cycle")
        
        return ", ".join(descriptions)

    def __add__(self, other: type["Remap"]):
        if not isinstance(other, Remap):
            return NotImplemented
        result = Remap()
        for src, dest in self.items():
            result[src] = other.get(dest, dest)
        for src, dest in other.items():
            if src not in result:
                result[src] = dest
        return Remap((k, v) for k, v in result.items() if k != v)

    def __neg__(self):
        result = Remap()
        for src, dest in self.items():
            result[dest] = src
        return result

    def __sub__(self, other):
        return self + (-other)

if __name__ == "__main__": # for testing
    import layout

    qwerty = layout.get_layout('qwerty')
    cmk = layout.get_layout('colemak')
    dh = layout.get_layout('colemak_dh')
    dh_ansi = layout.get_layout('colemak_ca_ansi')
    
    # print(layout_diff(cmk, dh))
    # print(repr(cmk))
    # print(repr(dh))

    dh_remap = layout_diff(cmk, dh)
    print(dh_remap - dh_remap)

    print(layout_diff(qwerty, cmk))
    print(repr(qwerty))
    print(repr(cmk))

