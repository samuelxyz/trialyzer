# Object to represent a superset of swaps, cycles, row/column swaps, etc
# Remaps can be composed with each other using the + operator,
# and reversed using the - operator. Subtraction is also implemented but
# I have no clue when you would ever use that.

from __future__ import annotations
from typing import Container, Iterable, Sequence

from typing import TYPE_CHECKING

if TYPE_CHECKING:    
    from layout import Layout
    from fingermap import Pos, Row

def cycle(*args: tuple[str]):
    remap = Remap()
    for i in range(len(args)):
        remap[args[i]] = args[(i + 1) % len(args)]
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
    for ipos, key in initial.keys.items():
        try:
            if key in remap:
                continue
            tpos = target.positions[key]
            if ipos == tpos:
                continue
            dest = initial.keys[tpos]
            first = key
            while dest != first:
                remap[key] = dest
                key = dest
                dest = initial.keys[target.positions[key]]
        except KeyError:
            continue
    return remap

class Remap(dict):
    """Remap stored as {key: destination for all moved keys}"""
    
    def translate(self, ngram: Iterable[str]) -> tuple[str, ...]:
        return tuple(self.get(key, key) for key in ngram)

    def _parse(self) -> tuple[Iterable, Iterable]:
        """Returns (cycles, swaps)"""

        if not self:
            return ((),())
        
        sequences = []
        consumed = set()
        check_for_merging = False
        for first_key, next_key in self.items():
            if first_key in consumed:
                continue
            sequence = [first_key]
            while next_key != first_key:
                sequence.append(next_key)
                try:
                    next_key = self[next_key]
                    if next_key in consumed:
                        break
                except KeyError:
                    sequence.append("unknown")
                    check_for_merging = True
                    break
            sequences.append(sequence)
            consumed.update(sequence)

        while check_for_merging:
            remove = []
            for i in range(len(sequences)):
                if sequences[i][-1] == "unknown":
                    for sequence in sequences:
                        if sequence[-1] == sequences[i][0]:
                            remove.append(i)
                            sequence.extend(sequences[i][1:])
            for i in sorted(remove, reverse=True):
                sequences.pop(i)
            if not remove:
                break
            remove.clear()
        
        cycles = []
        swaps = []
        for sequence in sequences:
            if len(sequence) > 2:
                cycles.append(sequence)
            else:
                swaps.append(sequence)
        return (cycles, swaps)

    def __str__(self) -> str:
        if not self:
            return "no-op"

        descriptions = []
        cycles, swaps = self._parse()
        
        if swaps:
            src, dest = zip(*swaps)
            descriptions.append(f"{' '.join(src)} <-> {' '.join(dest)}")
        for cycle_ in cycles:
            descriptions.append(f"{' '.join(cycle_)} cycle")
        
        return ", ".join(descriptions)

    def __repr__(self) -> str:
        if not self:
            return "Remap()"
        
        descriptions = []
        cycles, swaps = self._parse()
        
        if swaps:
            src, dest = zip(*swaps)
            if len(src) > 1:
                descriptions.append(f"set_swap(({', '.join(repr(c) for c in src)}), " 
                    f"({', '.join(repr(c) for c in dest)}))")
            else:
                descriptions.append(f"swap({repr(src[0])}, {repr(dest[0])})")
        for cycle_ in cycles:
            descriptions.append(f"cycle({', '.join(repr(c) for c in cycle_)})")

        return " + ".join(descriptions)

    def __add__(self, other: type["Remap"]):
        if not isinstance(other, Remap):
            return NotImplemented
        result = Remap()
        for key, dest in other.items():
            result[key] = self.get(dest, dest)
        for key in self:
            if key not in result:
                result[key] = self[key]
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
    dv = layout.get_layout('dvorak')
    print(layout_diff(qwerty, dv))
