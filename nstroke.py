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
    

def describe_tristroke(ts: Tristroke): 
    """
All tags always appear if they apply, except where noted with "Only for ...".

Tags considering whole trigram:
- sft
- sfb (contains sfb, not sft)
- sfr (contains sfr, not sft)
- sfs (not sft)
- fsb (contains fsb)
- hsb (contains hsb)
- hand-change (reflecting one bigram of sfb. Only for sfb)
- in, out (reflecting one bigram of sfb, sfr, tutu; or both bigrams of rolll. Only for those)
- tutu
- alt
- rolll
- redir
- bad-redir (Only for redir)

Tags considering bigrams:
- (first, second)-(in, out, sfb, sfr, fsb, hsb, lsb, rcb)
- skip-(in, out)
- fss (contains fss)
- hss (contains hss)
- rcs (contains rcs)
    """

    tags = set()
    if Finger.UNKNOWN in ts.fingers:
        return ("unknown",)
    
    def bifinger_category(fingers: Sequence[Finger], coords: Sequence[Coord]):
        if Finger.UNKNOWN in fingers:
            return "unknown"
        if (fingers[0] > 0) != (fingers[1] > 0):
            return "alt"
        delta = abs(fingers[1]) - abs(fingers[0])
        if delta == 0:
            return "sfr" if coords[1] == coords[0] else "sfb"
        else:
            return "out" if delta > 0 else "in"

    def detect_scissor(i: int, j: int):
        HALF_SCISSOR_THRESHOLD = 0.5
        FULL_SCISSOR_THRESHOLD = 1.5

        if (ts.fingers[i] > 0) != (ts.fingers[j] > 0):
            return False
        if abs(ts.fingers[i] - ts.fingers[j]) != 1:
            return False
        dy = ts.coords[i].y - ts.coords[j].y
        if abs(dy) < HALF_SCISSOR_THRESHOLD:
            return False
        lower = j if dy > 0 else i
        if ts.fingers[lower].name[1] == "P" and abs(dy) > FULL_SCISSOR_THRESHOLD:
            return "fsb"
        if ts.fingers[lower].name[1] not in ("M", "R"):
            return False
        if abs(dy) < FULL_SCISSOR_THRESHOLD:
            return "hsb"
        return "fsb"
    
    def detect_lateral_stretch(i: int, j: int):
        """Must be adjacent fingers and not thumb."""
        LATERAL_STRETCH_THRESHOLD = 2.0

        if (ts.fingers[i] > 0) != (ts.fingers[j] > 0):
            return False
        if abs(ts.fingers[i] - ts.fingers[j]) != 1:
            return False
        if abs(ts.fingers[i]) == 1 or abs(ts.fingers[j]) == 1:
            return False
        if abs(ts.coords[i].x - ts.coords[j].x) < LATERAL_STRETCH_THRESHOLD:
            return False
        return True
    
    def detect_row_change(i: int, j: int):
        """Must be same hand and not same finger."""
        ROW_CHANGE_THRESHOLD = 0.5
        if (ts.fingers[i] > 0) != (ts.fingers[j] > 0):
            return False
        if (ts.fingers[i] == ts.fingers[j]):
            return False
        if abs(ts.coords[i].y - ts.coords[j].y) < ROW_CHANGE_THRESHOLD:
            return False
        return True
    
    first, skip, second = map(
        bifinger_category, 
        itertools.combinations(ts.fingers, 2),
        itertools.combinations(ts.coords, 2))
    
    tags.add(f"first-{first}")
    tags.add(f"second-{second}")
    if skip in ("in", "out"):
        tags.add(f"skip-{skip}")
    
    if skip in ("sfb", "sfr"):
        if first in ("sfb", "sfr"):
            tags.add("sft")
        else: 
            tags.add("sfs")
    elif first in ("sfb", "sfr"):
        tags.add(first)
        if second in ("in", "out"):
            tags.add(second)
    elif second in ("sfb", "sfr"):
        tags.add(second)
        if first in ("in", "out"):
            tags.add(first)
    
    if skip == "alt":
        if "sfb" not in (first, second) and "sfr" not in (first, second):
            tags.add("tutu")
            if "in" in (first, second):
                tags.add("in")
            else:
                tags.add("out")
        else:
            tags.add("hand-change")
    else:
        if first in ("in, out") and second in ("in, out"):
            if first == second:
                tags.add("rolll")
                tags.add(first)
            else:
                tags.add("redir")
                if Finger.LI not in ts.fingers and Finger.RI not in ts.fingers:
                    tags.add("bad-redir")
        elif first == "alt" and second == "alt":
            tags.add("alt") # includes sfs
        # else it's sfb or sfr
    
    if (s1 := detect_scissor(0, 1)):
        tags.add(s1)
        tags.add(f"first-{s1}")
    if (s2 := detect_scissor(1, 2)):
        tags.add(s2)
        tags.add(f"second-{s2}")    
    if (ss := detect_scissor(0, 2)):
        if "hsb" in ss:
            tags.add("hss")
        else:
            tags.add("fss")
    
    if detect_lateral_stretch(0, 1):
        tags.add("first-lsb")
        tags.add("lsb")
    if detect_lateral_stretch(1, 2):
        tags.add("second-lsb")
        tags.add("lsb")
    if detect_lateral_stretch(0, 2):
        tags.add("lss")
    
    if detect_row_change(0, 1):
        tags.add("first-rcb")
        tags.add("rcb")
    if detect_row_change(1, 2):
        tags.add("second-rcb")
        tags.add("rcb")
    if detect_row_change(0, 2):
        tags.add("rcs")

    if Finger.LT in ts.fingers or Finger.RT in ts.fingers:
        tags.add("thumb")

    if abs(ts.fingers[1]) == 1:
        tags.add("middle-thumb")

    return tags

if __name__ == "__main__":

    from collections import defaultdict
    from statistics import mean

    import layout
    from typingdata import TypingData

    qwerty = layout.get_layout("qwerty")
    td = TypingData("tanamr")
    all_known = td.exact_tristrokes_for_layout(qwerty)
    sf = td.tristroke_speed_calculator(qwerty)
    ts_to_cat = {}
    cat_to_ts = defaultdict(list)
    for ts in qwerty.all_nstrokes():
        cat = frozenset(describe_tristroke(ts))
        ts_to_cat[ts] = cat
        cat_to_ts[cat].append(ts)
    cat_times = {cat: mean(sf(ts)[0] for ts in strokes) for cat, strokes in cat_to_ts.items()}
    cat_samples = {cat: [0, len(cat_to_ts[cat])] for cat in cat_times}
    for ts in all_known:
        cat_samples[frozenset(describe_tristroke(ts))][0] += 1
    for cat in sorted(cat_times, key=lambda c: cat_times[c]):
        print(f'{cat_times[cat]:.2f} ms from {cat_samples[cat][0]}/{cat_samples[cat][1]} samples: {", ".join(sorted(list(cat)))}')