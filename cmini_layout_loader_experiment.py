import csv
import os
import json
import itertools

import layout
import corpus

with os.scandir("cmini-layouts/") as files:
    file_list = [f.path for f in files if f.is_file()]

def load_cmini_layout(path: str):
    """May raise ValueError for ill-behaved layouts
    returns layout, number of rows

    """

    with open(path) as f:
        ll = json.load(f)

    max_width = max(x['col'] for x in ll['keys'].values()) + 1
    max_height = max(x['row'] for x in ll['keys'].values()) + 1
    matrix = [[' ']*max_width for _ in range(max_height)]

    for char, info in ll['keys'].items():
        row = info['row']
        col = info['col']

        matrix[row][col] = char
    
    if len(matrix) > 3:
        matrix[3][0] = ' ' * 4 + matrix[3][0]

    matrix_str = '\n'.join(' '.join(x) for x in matrix)

    if ll["board"] == "angle":
        matrix_str += "\nfingermap: ansi_angle"

    return layout.Layout(ll["name"], False, matrix_str), len(matrix)

# print(repr(load_cmini_layout('cmini-layouts/inqwerted.json')))

def calc_dsfb(c: corpus.Corpus, l: layout.Layout):
    count = 0
    for finger, ps in l.fingermap.cols.items():
        if not finger:
            continue
        keys = (l.keys[p] for p in ps if p in l.keys)
        keys2 = tuple(k for k in keys if k in c.key_counts)
        for combo in itertools.product(keys2, keys2):
            count += c.dsfb[combo]
    return count / c.bigram_counts.total()

corpuses = {
    "exponential": corpus.Corpus("tr_quotes.txt", "", "", 
        dsfb_experiment=(0, 0, *(2**-n for n in range(7)))),
    "harmonic": corpus.Corpus("tr_quotes.txt", "", "", 
        dsfb_experiment=(0, 0, *(n**-1 for n in range(1, 8)))),
    "inverse square": corpus.Corpus("tr_quotes.txt", "", "", 
        dsfb_experiment=(0, 0, *(n**-2 for n in range(1, 8)))),
}
# print(c.dsfb.most_common(30))

layout_data = {} # layoutname: numrows, *dsfb according to each corpus
for fname in file_list:
    try:
        l, numrows = load_cmini_layout(fname)
        layout_data[l.name] = (numrows,
            *tuple(calc_dsfb(c, l) for c in corpuses.values())
        )
    except (ValueError, KeyError):
        continue

with open("output/dsfb_experiment.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(("layout", "num rows", *corpuses.keys()))
    for l, data in layout_data.items():
        w.writerow((l, *data))