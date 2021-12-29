import csv
import itertools
import operator
import statistics
from os import path
from typing import Sequence
from board import Coord
from fingermap import Finger

import typingtest
import curses
import curses.textpad
import layout
import gui_util

def main(stdscr: curses.window):
    
    startup_text = [
            "Commands:",
            "t[ype] <trigram>: Enter typing test",
            "l[ayout] [layout name]: Show or change active layout",
            "s[ave] [csvname]: Save tristroke data to /data/csvname.csv",
            "bis[trokes] [csvname]: Show bistroke stats for active layout",
            "q[uit]"
    ]
    
    curses.curs_set(0)

    height, width = stdscr.getmaxyx()
    titlebar = stdscr.subwin(1,width,0,0)
    titlebar.bkgd(" ", curses.A_REVERSE)
    titlebar.addstr("Trialyzer" + " "*(width-10))
    titlebar.refresh()
    content_win = stdscr.subwin(1, 0)

    height, width = content_win.getmaxyx()
    message_win = content_win.derwin(
        height-len(startup_text)-2, int(width/3), len(startup_text), 0)
    right_pane = content_win.derwin(
        height-len(startup_text)-2, int(width*2/3), len(startup_text), 
        int(width/3))
    input_win = content_win.derwin(height-2, 2)
    input_box = curses.textpad.Textbox(input_win, True)
    
    text_red = 1
    text_green = 2
    text_blue = 3
    curses.init_pair(text_red, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(text_green, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(text_blue, curses.COLOR_BLUE, curses.COLOR_BLACK)
    active_layout = layout.get_layout("qwerty")
    unsaved_typingtest_data = []

    def message(msg: str, color: int = 0):
        gui_util.insert_line_bottom(
            msg, message_win, curses.color_pair(color))
        message_win.refresh()

    def get_input() -> str:
        input_win.move(0,0)
        curses.curs_set(1)

        res = input_box.edit()

        input_win.clear()
        input_win.refresh()
        message("> " + res)
        return res

    while True:
        content_win.addstr(0, 0, "\n".join(startup_text))
        content_win.addstr(height-2, 0, "> ")
        content_win.refresh()

        input_win.clear()
        input_win.refresh()

        args = get_input().split()
        if not len(args):
            continue
        command = args.pop(0).lower()

        if command in ("q", "quit"):
            if unsaved_typingtest_data:
                message("Quit without saving? (y/n)", text_blue)
                if get_input().strip().lower() in ("y", "yes"):
                    return
                else:
                    continue
            return
        elif command in ("t", "type"):
            if not args:
                tristroke = "abc" # TODO: Automatically pick a trigram
            elif len(args[0]) == 3:
                tristroke = [char for char in args[0]]
            elif len(args) == 3:
                tristroke = args
            else:
                message("Malformed trigram", text_red)
                continue
            message("Starting typing test >>>", text_green)
            unsaved_typingtest_data.append(
                (active_layout.to_nstroke(tristroke),
                    typingtest.test(right_pane, tristroke, active_layout))
            )
            message("Finished typing test", text_green)
            input_win.clear()
        elif command in ("l", "layout"):
            layout_name = " ".join(args)
            if layout_name:
                try:
                    active_layout = layout.get_layout(layout_name)
                    message("Set " + layout_name + " as the active layout.",
                            text_green)
                except OSError:
                    message("That layout was not found.", text_red)
            else:
                message("Active layout: " + str(active_layout), text_blue)
        elif command in ("d", "debug"):
            gui_util.debug_win(message_win, "message_win")
            gui_util.debug_win(right_pane, "right_pane")
        elif command in ("s", "save"):
            if not unsaved_typingtest_data:
                message("No unsaved data", text_blue)
                continue
            if not args:
                filename = "default"
            else:
                filename = " ".join(args)
            data = load_csv_data(filename)
            for entry in unsaved_typingtest_data:
                tristroke: layout.Tristroke = entry[0]
                if tristroke not in data:
                    data[tristroke] = ([],[])
                data[tristroke][0].extend(entry[1][0])
                data[tristroke][1].extend(entry[1][1])
            unsaved_typingtest_data.clear()
            save_csv_data(data, filename)
            message("Data saved", text_green)
        elif command in ("bis", "bistrokes"):
            if not args:
                filename = "default"
            else:
                filename = " ".join(args)
            message("Crunching the numbers >>>", text_green)
            message_win.refresh()
            right_pane.clear()
            data = bistroke_category_data(get_medians_for_layout(
                load_csv_data(filename), active_layout))
            for category in sorted(data):
                display_out = "{:.<17}{:>6.1f} ms (n={})".format(
                    category, float(data[category][0]), data[category][1])
                gui_util.insert_line_bottom(display_out, right_pane)
            right_pane.refresh()
        else:
            message("Unrecognized command", text_red)            

def start_csv_row(tristroke: layout.Tristroke):
    """Order of returned data: note, fingers, coords"""
    
    result = [tristroke.note]
    result.extend(f.name for f in tristroke.fingers)
    result.extend(itertools.chain.from_iterable(tristroke.coords))
    return result

def load_csv_data(filename: str):
    """Returns a dict of the form:

    dict[Tristroke, 
        (speeds_01: list[float], speeds_12: list[float])
    ]
    """

    data = {}
    if not path.exists("data/" + filename + ".csv"):
        return data

    with open("data/" + filename + ".csv", "r", newline="") as csvfile:
        reader = csv.DictReader(csvfile, restkey="speeds")
        for row in reader:
            fingers = tuple(
                (Finger[row["finger" + str(n)]] for n in range(3)))
            coords = tuple(
                (Coord(float(row["x" + str(n)]), 
                       float(row["y" + str(n)])) for n in range(3)))
            tristroke = layout.Tristroke(row["note"], fingers, coords)
            if tristroke not in data:
                data[tristroke] = ([], [])
            for i, time in enumerate(row["speeds"]):
                data[tristroke][i%2].append(float(time))
    return data

def save_csv_data(data: dict, filename: str):
    header = [
        "note", "finger0", "finger1", "finger2",
        "x0", "y0", "x1", "y1", "x2", "y2"
    ]
    with open("data/" + filename + ".csv", "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for tristroke in data:
                row = start_csv_row(tristroke)
                row.extend(itertools.chain.from_iterable(
                    zip(data[tristroke][0], 
                        data[tristroke][1])))
                w.writerow(row)

def get_medians_for_layout(csv_data: dict, layout: layout.Layout):
    """Take csv data, find tristrokes that are applicable to the given layout,
    and obtain speeds_01, speeds_12, and speeds_02 as medians.
    
    Returns a dict[Tristroke, (float, float, float)]"""
    by_fingers = {} # dict[Finger, list[Tristroke]]
    speeds = {} # dict[Tristroke, (list[float], list[float])]
    medians = {}
    for tristroke in layout.all_nstrokes():
        if tristroke.fingers in by_fingers:
            by_fingers[tristroke.fingers].append(tristroke)
        else:
            by_fingers[tristroke.fingers] = [tristroke]
    for csv_tristroke in csv_data:
        for layout_tristroke in by_fingers[csv_tristroke.fingers]:
            if compatible(layout_tristroke, csv_tristroke):
                if layout_tristroke not in speeds:
                    speeds[layout_tristroke] = csv_data[csv_tristroke]
                else:
                    speeds[layout_tristroke][0].append(
                        csv_data[csv_tristroke][0])
                    speeds[layout_tristroke][1].append(
                        csv_data[csv_tristroke][1])
    for tristroke in speeds:
        speeds_01 = speeds[tristroke][0]
        speeds_12 = speeds[tristroke][1]
        speeds_02 = map(operator.add, speeds_01, speeds_12)
        medians[tristroke] = (
            statistics.median(speeds_01),
            statistics.median(speeds_12),
            statistics.median(speeds_02)
        )
    return medians

def compatible(a: layout.Tristroke, b: layout.Tristroke):
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

def bifinger_category(fingers: Sequence[Finger]):
    # Used by both bistroke_category() and tristroke_category()
    if Finger.UNKNOWN in fingers:
        return "unknown"
    elif (fingers[0] > 0) != (fingers[1] > 0):
        return "alt"

    delta = abs(fingers[1]) - abs(fingers[0])
    if delta == 0:
        return "sfb"
    else:
        return "roll.out" if delta > 0 else "roll.in"

def bistroke_category(nstroke: layout.Nstroke, 
                      index0: int = 0, index1: int = 1):
    category = bifinger_category((nstroke.fingers[index0],
                                  nstroke.fingers[index1]))
    if category.startswith("roll"):
        category += detect_scissor(nstroke, index0, index1)
    return category

def tristroke_category(tristroke: layout.Tristroke):
    if Finger.UNKNOWN in tristroke.fingers:
        return "unknown"
    first, skip, second = map(
        bifinger_category, itertools.combinations(tristroke.fingers, 2))
    if skip == "sfb":
        if first == "sfb":
            return "sft"
        if first.startswith("roll"):
            return "sfs.redirect" + detect_scissor_roll(tristroke)
        else:
            return "sfs.alt" + detect_scissor_skip(tristroke)
    elif first == "sfb":
        return "sfb." + second + detect_scissor(tristroke, 1, 2)
    elif second == "sfb":
        return "sfb." + first + detect_scissor(tristroke, 0, 1)
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

def detect_scissor(nstroke: layout.Nstroke, index0: int = 0, index1: int = 1):
    """Given that the keys (optionally specified by index) are typed with the 
    same hand, return \".scissor\" if neighboring fingers must reach coords 
    that are a distance of 2.0 apart or farther. Return an empty string 
    otherwise."""
    if abs(nstroke.fingers[index0] - nstroke.fingers[index1]) != 1:
        return ""
    vec = map(operator.sub, nstroke.coords[index0], nstroke.coords[index1])
    dist_sq = sum((n**2 for n in vec))
    return ".scissor" if dist_sq >= 4 else ""

def detect_scissor_roll(tristroke: layout.Tristroke):
    if detect_scissor(tristroke, 0, 1):
        if detect_scissor(tristroke, 1, 2):
            return ".scissor.twice"
        else:
            return ".scissor"
    elif detect_scissor(tristroke, 1, 2):
        return ".scissor"
    else:
        return ""

def detect_scissor_skip(tristroke: layout.Tristroke):
    if detect_scissor(tristroke, 0, 2):
        return ".scissor_skip"
    else:
        return ""

def detect_scissor_any(tristroke: layout.Tristroke):
    return detect_scissor_roll(tristroke) + detect_scissor_skip(tristroke)

def print_bistroke_categories(layoutname: str): # for debug
    lay = layout.get_layout(layoutname)
    categories = {bistroke_category(bistroke)
        for bistroke in lay.all_nstrokes(2)}
    for category in sorted(categories):
        print(category)

def print_tristroke_categories(layoutname: str): # for debug
    lay = layout.get_layout(layoutname)
    categories = {tristroke_category(tristroke) 
        for tristroke in lay.all_nstrokes()}
    for category in sorted(categories):
        print(category)

def bistroke_category_data(medians: dict):
    """Returns a 
    dict[category: string, (speed: float, num_samples: int)]
    where num_samples is the number of unique bistroke median speeds that have 
    been averaged to obtain the speed stat. num_samples is positive if speed 
    is obtained from known data, and negative if speed is estimated from 
    related data, which occurs if no known data is directly applicable.
    
    Note that medians is the output of get_medians_for_layout()."""
    known_medians = {} # dict[category, list[median]]
    for tristroke in medians:
        for indices in ((0, 1), (1, 2)):
            category = bistroke_category(tristroke, *indices)
            try:
                known_medians[category].append(medians[tristroke][indices[0]])
            except KeyError:
                known_medians[category] = [medians[tristroke][indices[0]]]
    
    # now estimate missing data
    all_medians = {} # dict[category, list[median]]
    is_estimate = {} # dict[category, bool]
    all_bistroke_categories = [
        "",
        "alt",
        "roll",
        "roll.in",
        "roll.in.scissor",
        "roll.out",
        "roll.out.scissor",
        "sfb"
    ]
    for category in all_bistroke_categories: # sorted general -> specific
        if category in known_medians:
            all_medians[category] = known_medians[category]
            is_estimate[category] = False
        else:
            all_medians[category] = []
            is_estimate[category] = True
            for subcategory in known_medians:
                if subcategory.startswith(category):
                    all_medians[category].extend(known_medians[subcategory])
                # There may be no subcategories with known data either. 
                # Hence the next stages
    
    # Assuming sfs is the limiting factor in a trigram, this may help
    if not all_medians["sfb"]:
        for tristroke in medians:
            if tristroke_category(tristroke).startswith("sfs"):
                all_medians["sfb"].append(medians[tristroke][2])
    
    all_bistroke_categories.reverse() # most specific first
    for category in all_bistroke_categories:
        if not all_medians[category]: # data needed
            for supercategory in all_bistroke_categories: # most specific first
                if (category.startswith(supercategory) and 
                        bool(all_medians[supercategory])):
                    all_medians[category] = all_medians[supercategory]
                    break
    # If there is still any category with no data at this point, that means
    # there was literally no data in ANY category. that's just a bruh moment

    result = {}
    for category in all_medians:
        try:
            mean = statistics.mean(all_medians[category])
        except statistics.StatisticsError:
            mean = 0 # bruh
        result[category] = (
            mean,
            -len(all_medians[category]) if is_estimate[category]
                else len(all_medians[category])
        )
    return result
                
def tristroke_category_data(csv_data: dict):
    """Returns a 
    dict[category: string, (speed: float, num_samples: int)]
    where num_samples is the number of unique tristroke median speeds that have 
    been averaged to obtain the speed stat. num_samples is positive if speed 
    is obtained from known data, and negative if speed is estimated from 
    related data, which occurs if no known data is directly applicable.
    
    Note that medians is the output of get_medians_for_layout()."""
    all_tristroke_categories = [
        "",
        "alt",
        "alt.in",
        "alt.in.scissor_skip",
        "alt.out",
        "alt.out.scissor_skip",
        "onehand",
        "onehand.in",
        "onehand.in.scissor",
        "onehand.in.scissor.twice",
        "onehand.out",
        "onehand.out.scissor",
        "onehand.out.scissor.twice",
        "redirect",
        "redirect.scissor",
        "redirect.scissor.scissor_skip",
        "redirect.scissor_skip",
        "roll",
        "roll.in",
        "roll.in.scissor",
        "roll.out",
        "roll.out.scissor",
        "scissor",
        "scissor.twice",
        "scissor_skip",
        "sfb",
        "sfb.alt",
        "sfb.roll.in",
        "sfb.roll.in.scissor",
        "sfb.roll.out",
        "sfb.roll.out.scissor",
        "sfs",
        "sfs.alt",
        "sfs.redirect",
        "sfs.redirect.scissor",
        "sfs.redirect.scissor.twice",
        "sft"
    ]

if __name__ == "__main__":
    curses.wrapper(main)