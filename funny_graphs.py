# This one uses matplotlib

from typing import Callable, Container

import matplotlib.pyplot as plt
import numpy as np

import typingdata
import layout
from nstroke import describe_tristroke

td = typingdata.TypingData("tanamr")
qwerty = layout.get_layout("qwerty")
all_known = td.exact_tristrokes_for_layout(qwerty)

def get_medians_of_tristroke_category(conditions: Callable[[Container[str]], bool]):
    totals = []
    for ts in all_known:
        if conditions(describe_tristroke(ts)):
            totals.append(td.tri_medians[ts][2])
    return totals

fig, ax = plt.subplots()
redir_nothumb_noscissor = lambda tags: "redir" in tags and "thumb" not in tags and "hsb" not in tags and "fsb" not in tags and "hss" not in tags and "fss" not in tags and "sfs" not in tags
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

    # "redir\nno thumb\nno scissor": lambda tags: "redir" in tags and "thumb" not in tags and "hsb" not in tags and "fsb" not in tags and "hss" not in tags and "fss" not in tags,
    # "redir\nno thumb\nsome scissor": lambda tags: "redir" in tags and "thumb" not in tags and not("hsb" not in tags and "fsb" not in tags and "hss" not in tags and "fss" not in tags),
    # "non bad redir\nthumb": lambda tags: "redir" in tags and "bad-redir" not in tags and "thumb" in tags,
    # "bad redir\nthumb": lambda tags: "bad-redir" in tags and "thumb" in tags,
    # "non bad redir\nno thumb": lambda tags: "redir" in tags and "bad-redir" not in tags and "thumb" not in tags,
    # "bad redir\nno thumb": lambda tags: "bad-redir" in tags and "thumb" not in tags,
    "no thumb redir\ncenter last": lambda tags: redir_nothumb_noscissor(tags) and (("first-in" in tags and "skip-in" in tags) or ("first-out" in tags and "skip-out" in tags)),
    "no thumb redir\nother": lambda tags: redir_nothumb_noscissor(tags) and not(("first-in" in tags and "skip-in" in tags) or ("first-out" in tags and "skip-out" in tags)),
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

for cat, discriminator in categories.items():
    print(f"\n{cat}")
    strokes = {qwerty.to_ngram(ts): td.tri_medians[ts][2] for ts in all_known if discriminator(describe_tristroke(ts))}
    for tg in sorted(strokes, key=lambda tg: strokes[tg]):
        print(f"{strokes[tg]:.2f} ms: {' '.join(tg)}")
