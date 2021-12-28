import csv
import itertools
from os import path
from typing import Sequence
from board import Coord
from fingermap import Finger
from operator import sub as subtract

import typingtest
import curses
import curses.textpad
import layout
import gui_util

def main(stdscr: curses.window):
    
    startup_text = [
            "Commands:",
            "[t]ype <trigram>: Enter typing test",
            "[l]ayout [layout name]: Show or change active layout",
            "[s]ave [filename]: Save tristroke data to /data/filename.csv",
            "[q]uit"
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
                (active_layout.to_tristroke(tristroke),
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
                fingers = tristroke.fingers
                if fingers not in data:
                    data[fingers] = {}
                if entry[0] not in data[fingers]:
                    data[fingers][tristroke] = ([],[])
                data[fingers][tristroke][0].extend(entry[1][0])
                data[fingers][tristroke][1].extend(entry[1][1])
            unsaved_typingtest_data.clear()
            save_csv_data(data, filename)
            message("Data saved", text_green)

def start_csv_row(tristroke: layout.Tristroke):
    """Order of returned data: note, fingers, coords"""
    
    result = [tristroke.note]
    result.extend(f.name for f in tristroke.fingers)
    result.extend(itertools.chain.from_iterable(tristroke.coords))
    return result

def load_csv_data(filename: str):
    """Returns a dict of the form:

    dict[Tristroke.fingers, 
         dict[Tristroke, 
              (speeds_01: list[float], speeds_12: list[float])
         ]
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
                (Coord(row["x" + str(n)], 
                       row["y" + str(n)]) for n in range(3)))
            tristroke = layout.Tristroke(row["note"], fingers, coords)
            if fingers not in data:
                data[fingers] = {}
            if tristroke not in data[fingers]:
                data[fingers][tristroke] = ([], [])
            for i, time in enumerate(row["speeds"]):
                data[fingers][tristroke][i%2].append(time)
    return data

def save_csv_data(data: dict, filename: str):
    header = [
        "note", "finger0", "finger1", "finger2",
        "x0", "y0", "x1", "y1", "x2", "y2"
    ]
    with open("data/" + filename + ".csv", "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for fingers in data:
                for tristroke in data[fingers]:
                    row = start_csv_row(tristroke)
                    row.extend(itertools.chain.from_iterable(
                        zip(data[fingers][tristroke][0], 
                            data[fingers][tristroke][1])))
                    w.writerow(row)

def bifinger_category(fingers: Sequence[Finger]):
    if Finger.UNKNOWN in fingers:
        return "unknown"
    elif (fingers[0] > 0) != (fingers[1] > 0):
        return "alt"

    delta = abs(fingers[1]) - abs(fingers[0])
    if delta == 0:
        return "sfb"
    else:
        return "roll.out" if delta > 0 else "roll.in"

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

def detect_scissor(tristroke: layout.Tristroke, index0: int, index1: int):
    """Given that the specified keys in the tristroke are typed with the same 
    hand, return \".scissor\" if neighboring fingers must reach coords that are
    a distance of 2.0 apart or farther. Return an empty string otherwise."""
    if abs(tristroke.fingers[index0] - tristroke.fingers[index1]) != 1:
        return ""
    vec = map(subtract, tristroke.coords[index0], tristroke.coords[index1])
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

def print_tristroke_categories(layoutname: str): # for debug
    lay = layout.get_layout(layoutname)
    trigrams = itertools.combinations(lay.keys.values(), 3)
    tristrokes = (lay.to_tristroke(trigram) for trigram in trigrams)
    categories = {tristroke_category(tristroke) for tristroke in tristrokes}
    for category in sorted(list(categories)):
        print(category)

if __name__ == "__main__":
    curses.wrapper(main)