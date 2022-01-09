from typing import Counter
from trialyzer import *
import timeit

# ok what is the chain here
# note vscode debugger makes this roughly 10x slower than straight Python

# layout things
    # layout construction: 0.3 ms
    # calculate_counts: 1798 ms (includes all_nstrokes)
        # just a plain Counter instead (without calculating sums): 1878 ms
        # after making all the nstroke category functions @functools.cache: 
            # calculate_counts: 1266 ms
            # Counter(): 1348 ms
    # ngram to nstroke: 
    # how long does it take to iterate all tristrokes
        # tuple(all_nstrokes()): 1416 ms
            # after caching to_nstroke(): 275 ms!!
        # tuple(itertools all trigrams): 3 ms
        # Very interesting, seems like to_nstroke is the big deal. Cache it?
        # After unwrapping layout.finger() and .coord() from their functions:
            # tuple(all_nstrokes()): 1359 ms
        # After making dedicated dictionaries to replace the functions:
            # tuple(all_nstrokes()): 1216 ms

# trialyzer things
    # stuff that only runs through what is saved
        # load csv data: 3 ms
        # get medians: 125 ms
        # tristroke_category_data: 14 ms
    # runs through all tristrokes
        # summary_tristroke_analysis: 1923 ms
    # load shai: 162 ms
    # summary tristroke rank 3 layouts: 3687 ms
        # after caching layout.to_nstroke(): 1069 ms!!
    # full tristroke rank 3 layouts: 4897 ms
        # after caching layout.to_nstroke(): 1206 ms!!

# nstroke things
    # tristroke_category: 180 ms to go through a precomputed list of qwerty nstrokes

# csvdata = load_csv_data("default")
qwerty = layout.get_layout("qwerty")
# medians = get_medians_for_layout(csvdata, qwerty)
# tricatdata = tristroke_category_data(medians)
# data = summary_tristroke_analysis(qwerty, tricatdata, medians)

def stuff():
    # csvdata = load_csv_data("default")
    # for layoutname in ("qwerty", "semimak", "boom"):
    #     lay = layout.get_layout(layoutname)
    #     medians = get_medians_for_layout(csvdata, lay)
    #     tricatdata = tristroke_category_data(medians)
    #     summary_tristroke_analysis(lay, tricatdata, medians)
    tuple(qwerty.all_nstrokes())

n = 10
print(timeit.timeit("stuff()", globals=globals(), number=n)/n * 1000)