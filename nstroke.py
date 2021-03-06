import itertools
from typing import Sequence, Callable, NamedTuple, Tuple
import operator
import functools

from board import Coord
from fingermap import Finger

# Tristroke = collections.namedtuple("Tristroke", "note fingers coords")
class Tristroke(NamedTuple):
    note: str
    fingers: Tuple[Finger, ...]
    coords: Tuple[Coord, ...]
Nstroke = Tristroke

def bistroke(tristroke: Tristroke, index0: int, index1: int):
    # TODO: special handling for slides, altfingers etc
    return Nstroke(tristroke.note, 
        (tristroke.fingers[index0], tristroke.fingers[index1]),
        (tristroke.coords[index0], tristroke.coords[index1]))

# If category starts or ends with ".", it's purely a sum of others
# Note that order is important; supercategories before their subcategories
all_bistroke_categories = [
    "",
    "alt",
    "roll.",
    "roll.in",
    "roll.in.scissor",
    "roll.out",
    "roll.out.scissor",
    "sfb",
    "sfr",
    "unknown"
]
all_tristroke_categories = [
    "",
    ".scissor",
    ".scissor.twice",
    ".scissor_and_skip",
    ".scissor_skip",
    "alt.",
    "alt.in",
    "alt.in.scissor_skip",
    "alt.out",
    "alt.out.scissor_skip",
    "onehand.",
    "onehand.in",
    "onehand.in.scissor",
    "onehand.in.scissor.twice",
    "onehand.out",
    "onehand.out.scissor",
    "onehand.out.scissor.twice",
    "redirect",
    "redirect.scissor",
    "redirect.scissor_and_skip",
    "redirect.scissor_skip",
    "roll.",
    "roll.in",
    "roll.in.scissor",
    "roll.out",
    "roll.out.scissor",
    "sfb.",
    "sfb.alt",
    "sfb.roll.in",
    "sfb.roll.in.scissor",
    "sfb.roll.out",
    "sfb.roll.out.scissor",
    "sfr.",
    "sfr.alt",
    "sfr.roll.in",
    "sfr.roll.in.scissor",
    "sfr.roll.out",
    "sfr.roll.out.scissor",
    "sfs.",
    "sfs.alt",
    "sfs.redirect",
    "sfs.redirect.scissor",
    "sfs.redirect.scissor.twice",
    "sfs.trill",
    "sfs.trill.scissor.twice",
    "sft",
    "unknown"
]
category_display_names = {
    "": "total",
    "alt.": "alt",
    "onehand.": "onehand",
    "roll.": "roll",
    ".scissor": "*.scissor",
    ".scissor.twice": "*.scissor.twice",
    ".scissor_and_skip": "*.scissor_and_skip",
    ".scissor_skip": "*.scissor_skip",
    "sfb.": "sfb",
    "sfr.": "sfr",
    "sfs.": "sfs"
}
hand_names = {
    "R": "right hand total",
    "L": "left hand total",
}
finger_names = {
    "T": "thumb total",
    "I": "index total",
    "M": "middle total",
    "R": "ring total",
    "P": "pinky total"
}

def applicable_function(target_category: str) -> Callable[[str], bool]:
    """Given a target category, returns a function(category: str) which tells
    whether category is applicable to target_category.
    """
    if target_category.endswith("."):
        return lambda cat: cat.startswith(target_category)
    elif target_category.startswith("."):
        return lambda cat: cat.endswith(target_category)
    elif not target_category:
        return lambda _: True
    else:
        return lambda cat: cat == target_category

@functools.cache
def compatible(a: Tristroke, b: Tristroke):
    """Assumes it is already known that a.fingers == b.fingers.
    
    Tristrokes are compatible if they are equal, or if 
    there exists a pair of floats c1 and c2, which when added
    to the x-coords of the left and right hands respectively, 
    cause the tristrokes to become equal."""
    if a == b:
        return True
    for ac, bc in zip(a.coords, b.coords):
        if ac.y != bc.y:
            return False
    for i, j in itertools.combinations(range(3), 2):
        if (a.fingers[i] > 0) == (a.fingers[j] > 0):
            if ((a.coords[i].x - a.coords[j].x) !=
                    (b.coords[i].x - b.coords[j].x)):
                return False
    return True

@functools.cache
def bifinger_category(fingers: Sequence[Finger], coords: Sequence[Coord]):
    # Used by both bistroke_category() and tristroke_category()
    if Finger.UNKNOWN in fingers:
        return "unknown"
    elif (fingers[0] > 0) != (fingers[1] > 0):
        return "alt"

    delta = abs(fingers[1]) - abs(fingers[0])
    if delta == 0:
        return "sfr" if coords[1] == coords[0] else "sfb"
    else:
        return "roll.out" if delta > 0 else "roll.in"

@functools.cache
def bistroke_category(nstroke: Nstroke, 
                      index0: int = 0, index1: int = 1):
    category = bifinger_category(
        (nstroke.fingers[index0], nstroke.fingers[index1]),
        (nstroke.coords[index0], nstroke.coords[index1]))
    if category.startswith("roll"):
        category += detect_scissor(nstroke, index0, index1)
    return category

@functools.cache
def tristroke_category(tristroke: Tristroke):
    if Finger.UNKNOWN in tristroke.fingers:
        return "unknown"
    first, skip, second = map(
        bifinger_category, 
        itertools.combinations(tristroke.fingers, 2),
        itertools.combinations(tristroke.coords, 2))
    if skip in ("sfb", "sfr"):
        if first in ("sfb", "sfr"):
            return "sft"
        if first.startswith("roll"):
            if skip == "sfr":
                return "sfs.trill" + detect_scissor_roll(tristroke)
            else:
                return "sfs.redirect" + detect_scissor_roll(tristroke)
        else:
            return "sfs.alt" + detect_scissor_skip(tristroke)
    elif first in ("sfb", "sfr"):
        return first + "." + second + detect_scissor(tristroke, 1, 2)
    elif second in ("sfb", "sfr"):
        return second + "." + first + detect_scissor(tristroke, 0, 1)
    elif first == "alt" and second == "alt":
        return "alt" + skip[4:] + detect_scissor_skip(tristroke)
    elif first.startswith("roll"):
        if second.startswith("roll"):
            if first == second:
                return "onehand" + first[4:] + detect_scissor_roll(tristroke)
            else:
                return "redirect" + detect_scissor_any(tristroke)
        else:
            return first + detect_scissor(tristroke, 0, 1) # roll
    else: # second.startswith("roll")
        return second + detect_scissor(tristroke, 1, 2) # roll

@functools.cache
def detect_scissor(nstroke: Nstroke, index0: int = 0, index1: int = 1):
    """Given that the keys (optionally specified by index) are typed with the 
    same hand, return \".scissor\" if neighboring fingers must reach coords 
    that are a distance of 2.0 apart or farther. Return an empty string 
    otherwise."""
    if abs(nstroke.fingers[index0] - nstroke.fingers[index1]) != 1:
        return ""
    thumbs = (Finger.LT, Finger.RT)
    if nstroke.fingers[index0] in thumbs or nstroke.fingers[index1] in thumbs:
        return ""
    vec = map(operator.sub, nstroke.coords[index0], nstroke.coords[index1])
    dist_sq = sum((n**2 for n in vec))
    return ".scissor" if dist_sq >= 4 else ""

@functools.cache
def detect_scissor_roll(tristroke: Tristroke):
    if detect_scissor(tristroke, 0, 1):
        if detect_scissor(tristroke, 1, 2):
            return ".scissor.twice"
        else:
            return ".scissor"
    elif detect_scissor(tristroke, 1, 2):
        return ".scissor"
    else:
        return ""

@functools.cache
def detect_scissor_skip(tristroke: Tristroke):
    if detect_scissor(tristroke, 0, 2):
        return ".scissor_skip"
    else:
        return ""

@functools.cache
def detect_scissor_any(tristroke: Tristroke):
    cat = detect_scissor_roll(tristroke) + detect_scissor_skip(tristroke)
    return ".scissor_and_skip" if cat == ".scissor.scissor_skip" else cat
    