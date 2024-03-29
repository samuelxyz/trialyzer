import curses
from typing import Iterable
import statistics
import math

def extreme(seq):
    return max(abs(val) for val in seq)
def neg_extreme(seq):
    return -max(abs(val) for val in seq)
def odd_sqrt(n):
    return math.sqrt(n) if n >= 0 else -math.sqrt(-n)

red = 1
green = 2
blue = 3
gray = 4

gradient_colors = (196, 202, 208, 214, 220, 226, 190, 154, 118, 82, 46)

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    bg = -1
    # bg = curses.COLOR_BLACK
    curses.init_pair(red, curses.COLOR_RED, bg)
    curses.init_pair(green, curses.COLOR_GREEN, bg)
    curses.init_pair(blue, curses.COLOR_CYAN, bg)
    curses.init_pair(gray, 244, bg)

    # n = gradient_colors + 8
    # m = min_gradient_color - 4
    # for i in range(n): # colors for worst to best
    #     curses.init_color(
    #         m+i, 
    #         int(1000*(1-i/n)), 
    #         int(1000*(1-2*abs(i/n-0.5))), 
    #         int(1000*(i/n))
    #     )
        # curses.init_pair(m+i, m+i, curses.COLOR_BLACK)

    for i in range(5, curses.COLOR_PAIRS):
        curses.init_pair(i, i, bg)

def color_scale(worst, best, target, exclude_zeros = False):
    """Make sure to run the result through curses.color_pair()."""
    if exclude_zeros and not target: return gray
    if best == worst:
        if target > best: return gradient_colors[-1]
        elif target < best: return gradient_colors[0]
        else: return gradient_colors[int(len(gradient_colors)/2)]
    fraction = (target-worst) / (best-worst)
    if fraction < 0:
        fraction = 0
    elif fraction >= 1.0:
        fraction = 0.999
    i = int(len(gradient_colors)*fraction)
    return gradient_colors[i]

def apply_scales(rows: dict[str, Iterable], col_settings: Iterable[dict]):
    """Applies scale to each column of a table and returns a result, which is 
    accessed by result[col][rowname], giving the curses color pair for each 
    entry in the table.

    rows is a dict containing {rowname: (data0, data1, ..., dataN)}.
    col_settings is of length N, each entry being a dict with the keywords:
    "worst", "best", "scale_filter", "transform", "exclude_zeros". 
    Defaults to min, max, lambda _: True, lambda x: x, True.
    "worst" and "best" are applied before the transform.
    
    Columns whose col_settings entry is None, or nonexistent, will be skipped
    and the corresponding column in the output will be None or nonexistent
    respectively."""
    if not rows:
        return dict()
    pairs = [dict() for _ in col_settings]
    defaults = {"worst": min, "best": max, "scale_filter": lambda _: True, 
        "transform": lambda x: x, "exclude_zeros": True}
    for col, settings in enumerate(col_settings):
        if settings is None:
            pairs[col] = None
            continue
        for key in defaults:
            if key not in settings:
                settings[key] = defaults[key]
        if settings["exclude_zeros"]:
            def zeros_filter(x): return x != 0
        else:
            def zeros_filter(_): return True
        try:
            worst = settings["transform"](
                settings["worst"](val[col] for val in rows.values()
                    if settings["scale_filter"](val[col])
                    and zeros_filter(val[col])))
            best = settings["transform"](
                settings["best"](val[col] for val in rows.values()
                    if settings["scale_filter"](val[col])
                    and zeros_filter(val[col])))
        except ValueError: # no valid values
            worst = 0.0
            best = 0.0
        for rowname in rows:
            pairs[col][rowname] = curses.color_pair(color_scale(
                worst, best, settings["transform"](rows[rowname][col]),
                settings["exclude_zeros"]))
    return pairs

def MAD_z(zscore: float, keep_within_data_values: bool = True):
    """This is intended as an less outlier-sensitive alternative to 
    max() and min().
    
    Returns a function which, given a distribution, returns the value
    that would have the specified "z-score". Not a conventional z-score, as
    it uses Median Absolute Deviation (median deviation from the median)
    instead of standard deviation."""
    
    def func(data: Iterable):
        data = tuple(data)
        if not data:
            return 0.0
        median = statistics.median(data)
        diffs = tuple(abs(d - median) for d in data)
        mad = statistics.median(diffs)
        raw = median + zscore*mad
        if not keep_within_data_values:
            return raw
        else:
            if zscore > 0:
                return min(raw, max(data))
            else:
                return max(raw, min(data))

    return func


def insert_line_bottom(text: str, win: curses.window, attr: int = ...):
    """Scrolls a line in from the bottom of the window. 
    Wraps overflow onto subsequent lines.
    Does not refresh the window.
    """
    if "\n" in text:
        for subtext in text.split("\n"):
            insert_line_bottom(subtext, win, attr)
        return
    
    ymax, xmax = win.getmaxyx()

    while len(text) > xmax-1:
        first_line = text[:xmax-1]
        text = text[xmax-1:]
        insert_line_bottom(first_line, win, attr)

    # win.scrollok(True)
    # win.idlok(True)
    win.scroll(1)

    if attr != ...:
        win.addstr(ymax-1, 0, text, attr)
    else:
        win.addstr(ymax-1, 0, text)

def debug_win(win: curses.window, label: str):
    win.border()
    for i in range(win.getmaxyx()[0]):
        win.addstr(i, 0, str(i) + " ")
    win.addstr(0, 0, label + " 0,0")
    win.refresh()