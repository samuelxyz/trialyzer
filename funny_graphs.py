# This one uses matplotlib

from typing import Sequence, Callable, Container
import itertools

import matplotlib.pyplot as plt
import numpy as np

import typingdata
import layout
from board import Coord
from nstroke import Tristroke, Finger

td = typingdata.TypingData("tanamr")
all_known = td.exact_tristrokes_for_layout(layout.get_layout("qwerty"))

def get_medians_of_tristroke_category(conditions: Callable[[Container[str]], bool]):
    totals = []
    for ts in all_known:
        if conditions(describe_tristroke(ts)):
            totals.append(td.tri_medians[ts][2])
    return totals

def describe_tristroke(ts: Tristroke): 
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
            return ()
        if abs(ts.fingers[i] - ts.fingers[j]) != 1:
            return ()
        dy = ts.coords[i].y - ts.coords[j].y
        if abs(dy) < HALF_SCISSOR_THRESHOLD:
            return ()
        lower = j if dy > 0 else i
        if ts.fingers[lower].name[1] == "P" and abs(dy) > FULL_SCISSOR_THRESHOLD:
            return ("fsb",)
        if ts.fingers[lower].name[1] not in ("M", "R"):
            return ()
        if abs(dy) < FULL_SCISSOR_THRESHOLD:
            return ("hsb",)
        return ("fsb",)
    
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
                tags.add("first-"+first)
                if skip in ("in", "out"):
                    tags.add("skip-"+skip)
        elif first == "alt" and second == "alt":
            tags.add("alt") # includes sfs
            if skip in ("in", "out"):
                tags.add("skip-"+skip) # inward and outward alternation
        # else it's sfb or sfr
    
    tags.update(detect_scissor(0, 1))
    tags.update(detect_scissor(1, 2))
    ss = detect_scissor(0, 2)
    if ss:
        if "hsb" in ss:
            tags.add("hss")
        else:
            tags.add("fss")
    
    if detect_lateral_stretch(0, 1) or detect_lateral_stretch(1, 2):
        tags.add("lsb")
    if detect_lateral_stretch(0, 2):
        tags.add("lss")
    
    if detect_row_change(0, 1) or detect_row_change(1, 2):
        tags.add("rcb")
    if detect_row_change(0, 2):
        tags.add("rcs")

    if Finger.LT in ts.fingers or Finger.RT in ts.fingers:
        tags.add("thumb")

    if abs(ts.fingers[1]) == 1:
        tags.add("middle-thumb")

    return tags

fig, ax = plt.subplots()
categories = {
    # "sfs redir": lambda tags: "sfs" in tags and "redir" in tags,
    # "all redir": lambda tags: "redir" in tags,
    # "non-scissor\nonehand": lambda tags: "rolll" in tags and "hsb" not in tags and "fsb" not in tags,
    # "roll AND NOT\nrowchange": lambda tags: "tutu" in tags and "rcb" not in tags,
    # "roll AND\nrowchange": lambda tags: "tutu" in tags and "rcb" in tags,
    # "roll AND\nHSB": lambda tags: "tutu" in tags and "hsb" in tags,
    # "roll AND\nFSB": lambda tags: "tutu" in tags and "fsb" in tags,
    # "non-sfs\nredir": lambda tags: "redir" in tags and "sfs" not in tags,
    # "non-sfs\nbad redir": lambda tags: "bad-redir" in tags and "sfs" not in tags,
    # "alt AND\nNOT sfs": lambda tags: "alt" in tags and "sfs" not in tags,
    # "alt AND sfs": lambda tags: "alt" in tags and "sfs" in tags,
    # "sfs": lambda tags: "sfs" in tags,
    # "sfb": lambda tags: "sfb" in tags,
    # # "sft": lambda tags: "sft" in tags,
    # "roll-in": lambda tags: "tutu" in tags and "in" in tags,
    # "roll-out": lambda tags: "tutu" in tags and "out" in tags,

    # "redir with\nthumb": lambda tags: "redir" in tags and "thumb" in tags,
    # "redir without\nthumb": lambda tags: "redir" in tags and "thumb" not in tags,
    # "non-sfs\nredir without\nthumb": lambda tags: "redir" in tags and "thumb" not in tags and "sfs" not in tags,
    # "roll with\nthumb": lambda tags: "tutu" in tags and "thumb" in tags,
    # "roll without\nthumb": lambda tags: "tutu" in tags and "thumb" not in tags,

    # "roll AND lsb": lambda tags: "tutu" in tags and "lsb" in tags,
    # "roll AND lsb\nAND scissor": lambda tags: "tutu" in tags and "lsb" in tags and ("hsb" in tags or "fsb" in tags),
    # "roll AND\nNOT lsb": lambda tags: "tutu" in tags and "lsb" not in tags,

    # "thumb redir\nfirst-in\nskip-in": lambda tags: "redir" in tags and "first-in" in tags and "skip-in" in tags and "thumb" in tags,
    # "thumb redir\nfirst-in\nskip-out": lambda tags: "redir" in tags and "first-in" in tags and "skip-out" in tags and "thumb" in tags,
    # "thumb redir\nfirst-out\nskip-in": lambda tags: "redir" in tags and "first-out" in tags and "skip-in" in tags and "thumb" in tags,
    # "thumb redir\nfirst-out\nskip-out": lambda tags: "redir" in tags and "first-out" in tags and "skip-out" in tags and "thumb" in tags,
    # "non-thumb redir\nfirst-in\nskip-in": lambda tags: "redir" in tags and "first-in" in tags and "skip-in" in tags and "thumb" not in tags,
    # "non-thumb redir\nfirst-in\nskip-out": lambda tags: "redir" in tags and "first-in" in tags and "skip-out" in tags and "thumb" not in tags,
    # "non-thumb redir\nfirst-out\nskip-in": lambda tags: "redir" in tags and "first-out" in tags and "skip-in" in tags and "thumb" not in tags,
    # "non-thumb redir\nfirst-out\nskip-out": lambda tags: "redir" in tags and "first-out" in tags and "skip-out" in tags and "thumb" not in tags,

    # "middle thumb\nredir": lambda tags: "redir" in tags and "middle-thumb" in tags,
    # "end thumb\nredir": lambda tags: "redir" in tags and "middle-thumb" not in tags and "thumb" in tags,    
    # "redir without\nthumb": lambda tags: "redir" in tags and "thumb" not in tags,

    "redir\nno thumb\nno scissor": lambda tags: "redir" in tags and "thumb" not in tags and "hsb" not in tags and "fsb" not in tags and "hss" not in tags and "fss" not in tags,
    "redir\nno thumb\nsome scissor": lambda tags: "redir" in tags and "thumb" not in tags and not("hsb" not in tags and "fsb" not in tags and "hss" not in tags and "fss" not in tags),
}
datas = [np.array(get_medians_of_tristroke_category(func)) for func in categories.values()]
ax.violinplot(datas, showmedians=True, quantiles=[[0.25, 0.75] for _ in datas])
ax.set_xticks([y+1 for y in range(len(datas))],
              labels=list(categories), rotation=0)
ax.set_ylabel("Trigram times (ms)")
ax.set_title("Using trigrams typed in isolation")
pos = np.arange(len(datas)) + 1
for tick, label in zip(range(len(datas)), ax.get_xticklabels()):
    ax.text(pos[tick], .97, f"n={len(datas[tick])}",
             transform=ax.get_xaxis_transform(),
             horizontalalignment='center', size='x-small')

plt.show()