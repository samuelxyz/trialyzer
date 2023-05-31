# `Command`s bundle names/aliases, help-strings, and functionality.
# Also defines all the individual commands in trialyzer.
# Also contains backend functions which are useful for the commands.

import curses
import enum
import math
import os
from typing import Callable

from fingermap import Finger
from nstroke import category_display_names, hand_names, finger_names
from session import Session
import gui_util

class CommandType(enum.Enum):
    GENERAL = enum.auto()
    DATA = enum.auto()
    ANALYSIS = enum.auto()
    EDITING = enum.auto()

class Command:    
    
    def __init__(self, type: CommandType, help: str, names: tuple[str], 
                 fn: Callable[[tuple[str], Session], str | None]):
        """
        `names` is a list of aliases that the user can use to activate the 
        command. 
        
        `help` may contain newlines; the first line will be used as a brief 
        summary when the `help` command is used with no args. 
        
        `fn` is the actual function to be run, with parameters being 
        `args: str` and `session`. It is usually void, but may return `"quit"`
        to trigger application exit.
        """
        self.names = names
        self.type = type
        self.help = help
        self.fn = fn

commands = list()
by_name = dict()

def register_command(cmd: Command):
    commands.append(cmd)
    for name in cmd.names:
        by_name[name] = cmd

def run_command(name: str, args: tuple[str], s: Session):
    cmd = by_name.get(name, None)
    if cmd is None:
        s.say("Unrecognized command", gui_util.red)
    else:
        return cmd(args, s)
    
# Actual commands


    
# Helper functions

def print_stroke_categories(s: Session, data: dict, counts: dict = None):
    s.right_pane.scroll(len(data))
    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - len(data)

    p_pairs = {} # proportion completed
    s_pairs = {} # speeds
    c_pairs = {} # total count

    # setup & calcs
    if counts:
        # log causes better usage of the gradient
        log_counts = {cat: math.log(counts[cat]) 
            if counts[cat] else 0 for cat in counts}
        cmin = min(filter(None, log_counts.values()))
        cmax = max(log_counts.values())
        completion = {}
        for category in data:
            if data[category][1] > 0 and counts[category]:
                # sqrt makes smaller differences more visible
                completion[category] = math.sqrt(
                    data[category][1]/counts[category])
            else:
                completion[category] = 0
        madm5 = gui_util.MAD_z(-5.0)
        mad5 = gui_util.MAD_z(5.0)
        for category in data:
            p_pairs[category] = curses.color_pair(gui_util.color_scale(
                madm5(filter(None, completion.values())), 
                mad5(completion.values()),
                completion[category], True))
            c_pairs[category] = curses.color_pair(gui_util.color_scale(
                cmin, cmax, log_counts[category], True))
    else:
        for category in data:
            p_pairs[category] = curses.color_pair(0)

    for category in data:
        s_pairs[category] = curses.color_pair(gui_util.color_scale(
            max(val[0] for val in data.values()),
            min(val[0] for val in data.values()), 
            data[category][0]))
    
    # printing
    for category in sorted(data):
        category_name = (category_display_names[category] 
            if category in category_display_names else category)
        pad_char = " "
        if category.endswith(".") or not category:
            category_name += " (total)"
            pad_char = "-"
        if not category.startswith("."):
            if "." not in category_name:
                pad_char = "-"
                category_name += " "
        s.right_pane.addstr(
            row, 0, ("{:" + pad_char + "<26}").format(category_name))
        s.right_pane.addstr(
            row, 27, "{:>6.1f}".format(float(data[category][0])),
            s_pairs[category])
        s.right_pane.addstr(
            row, 36, "{:< 6}".format(data[category][1]),
            p_pairs[category])
        if counts:
            s.right_pane.addstr(
                row, 43, "/{:<6}".format(counts[category]), 
                c_pairs[category])
        row += 1
    
    s.right_pane.refresh()

def print_analysis_stats(s: Session, stats: dict, header_line: str, 
                         diff_mode: bool = False):
    # colors
    if diff_mode:
        col_settings = (
            {"transform": gui_util.odd_sqrt, "worst": gui_util.neg_extreme, "best": gui_util.extreme,
                "scale_filter": lambda val: val != stats[""][0]},
            {"transform": gui_util.odd_sqrt, "worst": gui_util.neg_extreme, "best": gui_util.extreme},
            {"worst": gui_util.extreme, "best": gui_util.neg_extreme},
            {"transform": gui_util.odd_sqrt, "worst": gui_util.extreme, "best": gui_util.neg_extreme,
                "scale_filter": lambda val: val != stats[""][3]},
        )
    else:
        col_settings = (
            {"transform": gui_util.odd_sqrt, 
                "scale_filter": lambda val: val != stats[""][0]},
            {"transform": gui_util.odd_sqrt},
            {"worst": max, "best": min},
            {"transform": gui_util.odd_sqrt, "worst": max, "best": min,
                "scale_filter": lambda val: val != stats[""][3]},
        )
    pairs = gui_util.apply_scales(stats, col_settings)

    gui_util.insert_line_bottom(header_line, s.right_pane)
    s.right_pane.scroll(len(stats))
    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - len(stats)

    # printing
    s = '+' if diff_mode else ''
    for category in sorted(stats):
        category_name = (category_display_names[category] 
            if category in category_display_names else category)
        pad_char = " "
        if category.endswith(".") or not category:
            category_name += " (total)"
            pad_char = "-"
        if not category.startswith("."):
            if "." not in category_name:
                pad_char = "-"
                category_name += " "
        s.right_pane.addstr( # category name
            row, 0, ("{:" + pad_char + "<26}").format(category_name))
        s.right_pane.addstr( # freq
            row, 27, f"{stats[category][0]:>{s}6.2%}",
            pairs[0][category])
        s.right_pane.addstr( # known_freq
            row, 36, f"{stats[category][1]:>{s}6.2%}",
            pairs[1][category])
        s.right_pane.addstr( # speed
            row, 45, f"{stats[category][2]:>{s}6.1f}",
            pairs[2][category])
        s.right_pane.addstr( # contrib
            row, 53, f"{stats[category][3]:>{s}6.2f}",
            pairs[3][category])
        row += 1
    
    s.right_pane.refresh()

def print_finger_stats(s: Session, stats: dict):
    # colors
    col_settings = (
        {"transform": math.sqrt},
        {"transform": math.sqrt},
        {"transform": math.sqrt},
        {"worst": max, "best": min},
        {"transform": math.sqrt, "worst": max, "best": min},
        )
    pairs = gui_util.apply_scales(stats, col_settings)

    categories = []
    categories.extend(
        name for name in hand_names.values() if name in stats)
    categories.extend(
        name for name in finger_names.values() if name in stats)
    categories.extend(
        finger.name for finger in Finger if finger.name in stats)

    longest = len(max(categories, key=len)) + 2

    header_line = (
            "-" * (longest-6) +
            " letter stats | tristroke stats ----------------"
            "\nCategory" + " " * (longest-8) + 
            "   freq |   freq    exact   avg_ms      ms"
    )

    gui_util.insert_line_bottom(header_line, s.right_pane)
    s.right_pane.scroll(len(stats))
    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - len(stats)

    # printing
    for category in categories:
        s.right_pane.addstr( # category name
            row, 0, f"{category:<{longest}}")
        s.right_pane.addstr( # lfreq
            row, longest+1, f"{stats[category][0]:>6.2%}",
            pairs[0][category])
        s.right_pane.addstr(row, longest+8, "|")
        s.right_pane.addstr( # tfreq
            row, longest+10, f"{stats[category][1]:>6.2%}",
            pairs[1][category])
        s.right_pane.addstr( # known
            row, longest+19, f"{stats[category][2]:>6.2%}",
            pairs[2][category])
        s.right_pane.addstr( # avg_ms
            row, longest+28, f"{stats[category][3]:>6.1f}",
            pairs[3][category])
        s.right_pane.addstr( # ms
            row, longest+36, f"{stats[category][4]:>6.2f}",
            pairs[4][category])
        row += 1
    
    s.right_pane.refresh()

def scan_dir(path: str = "layouts/.", exclude: str = "."):
    file_list = []
    with os.scandir(path) as files:
        for file in files:
            if exclude not in file.name and file.is_file():
                file_list.append(file.name)
    return file_list

# Command registration