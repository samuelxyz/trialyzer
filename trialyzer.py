import csv
import itertools
import operator
import statistics
import os
import math
import json

from board import Coord
from fingermap import Finger
from nstroke import *
import typingtest
import curses
import curses.textpad
import layout
import gui_util

def main(stdscr: curses.window):
    
    try:
        with open("session_settings.json") as settings_file:
            settings = json.load(settings_file)
        startup_layout_name = settings["active_layout_name"]
        active_speeds_file = settings["active_speeds_file"]
    except OSError:
        startup_layout_name = "qwerty"
        active_speeds_file = "default"

    active_layout = layout.get_layout(startup_layout_name)
    
    def startup_text(): 
        return [
            "\"h\" or \"help\" to show command list",
            f"Active layout: {active_layout}",
            f"Active speeds file: {active_speeds_file}"
            f" (/data/{active_speeds_file}.csv)"
        ]

    curses.curs_set(0)
    gui_util.init_colors()

    height, width = stdscr.getmaxyx()
    titlebar = stdscr.subwin(1,width,0,0)
    titlebar.bkgd(" ", curses.A_REVERSE)
    titlebar.addstr("Trialyzer" + " "*(width-10))
    titlebar.refresh()
    content_win = stdscr.subwin(1, 0)

    height, width = content_win.getmaxyx()
    startup_lines = len(startup_text())
    message_win = content_win.derwin(
        height-startup_lines-2, int(width/3), startup_lines, 0)
    right_pane = content_win.derwin(
        height-startup_lines-2, int(width*2/3), startup_lines, 
        int(width/3))
    for win in (message_win, right_pane):
        win.scrollok(True)
        win.idlok(True)
    input_win = content_win.derwin(height-2, 2)
    input_box = curses.textpad.Textbox(input_win, True)
    
    unsaved_typingtest_data = []

    def message(msg: str, color: int = 0, win: curses.window = message_win):
        gui_util.insert_line_bottom(
            msg, win, curses.color_pair(color))
        win.refresh()

    def get_input() -> str:
        input_win.move(0,0)
        curses.curs_set(1)

        res = input_box.edit()

        input_win.clear()
        input_win.refresh()
        message("> " + res)
        return res

    def print_stroke_categories(data: dict, counts: dict = None):
        right_pane.scroll(len(data))
        ymax = right_pane.getmaxyx()[0]
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
            for category in data:
                p_pairs[category] = curses.color_pair(gui_util.color_scale(
                    min(completion.values()), max(completion.values()),
                    completion[category]))
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
                category_name += " (total) "
                pad_char = "-"
            if not category.startswith("."):
                if "." not in category_name:
                    pad_char = "-"
                    category_name += " "
            right_pane.addstr(
                row, 0, ("{:" + pad_char + "<26}").format(category_name))
            right_pane.addstr(
                row, 27, "{:>6.1f}".format(float(data[category][0])),
                s_pairs[category])
            right_pane.addstr(
                row, 36, "{:< 6}".format(data[category][1]),
                p_pairs[category])
            if counts:
                right_pane.addstr(
                    row, 43, "/{:<6}".format(counts[category]), 
                    c_pairs[category])
            row += 1
        
        right_pane.refresh()
    
    def save_session_settings():
        with open("session_settings.json", "w") as settings_file:
            json.dump(
                {   "active_layout_name": active_layout.name,
                    "active_speeds_file": active_speeds_file,
                }, settings_file)

    while True:
        content_win.addstr(0, 0, "\n".join(startup_text()))
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
                message("Quit without saving? (y/n)", gui_util.blue)
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
                message("Malformed trigram", gui_util.red)
                continue
            message("Starting typing test >>>", gui_util.green)
            unsaved_typingtest_data.append(
                (active_layout.to_nstroke(tristroke),
                    typingtest.test(right_pane, tristroke, active_layout))
            )
            message("Finished typing test", gui_util.green)
            input_win.clear()
        elif command in ("l", "layout", "layouts"):
            layout_name = " ".join(args)
            if layout_name: # set layout
                try:
                    active_layout = layout.get_layout(layout_name)
                    message("Set " + layout_name + " as the active layout.",
                            gui_util.green)
                    save_session_settings()
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
            else: # list layouts
                layout_file_list = []
                with os.scandir("layouts/.") as files:
                    for file in files:
                        if "." not in file.name and file.is_file():
                            layout_file_list.append(file.name)
                if not layout_file_list:
                    message("No layouts found in /layouts/", gui_util.blue)
                    continue
                message(f"{len(layout_file_list)} layouts found >>>", gui_util.green)
                right_pane.scroll(1)
                message("Layouts:", win = right_pane)
                for name in layout_file_list:
                    message(name, win = right_pane)
        elif command in ("s", "save"):
            if not unsaved_typingtest_data:
                message("No unsaved data", gui_util.blue)
                continue
            data = load_csv_data(active_speeds_file)
            for entry in unsaved_typingtest_data:
                tristroke: Tristroke = entry[0]
                if tristroke not in data:
                    data[tristroke] = ([],[])
                data[tristroke][0].extend(entry[1][0])
                data[tristroke][1].extend(entry[1][1])
            unsaved_typingtest_data.clear()
            save_csv_data(data, active_speeds_file)
            message("Data saved", gui_util.green)
        elif command in ("a", "analyze"):
            if args:
                layout_name = " ".join(args)
                try:
                    target_layout = layout.get_layout(layout_name)
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
                    continue
            else:
                target_layout = active_layout
            message("Crunching the numbers >>>", gui_util.green)
            message_win.refresh()
            
            medians = get_medians_for_layout(
                load_csv_data(active_speeds_file), target_layout)
            stats = analyze_layout(target_layout, 
                                   tristroke_category_data(medians), medians)
            
            # color calcs
            pairs = [dict() for i in range(4)]
            wb = [None for i in range(4)]
            for i in (0,):
                wb[i] = (
                    math.sqrt(min(val[i] for val in stats.values())),
                    math.sqrt(max(stats[cat][i] for cat in stats if cat))
                )
                for category in stats:
                    pairs[i][category] = curses.color_pair(gui_util.color_scale(
                        *wb[i], math.sqrt(stats[category][i]), True
                    ))
            for i in (1,):
                wb[i] = (
                    math.sqrt(min(val[i] for val in stats.values())),
                    math.sqrt(max(val[i] for val in stats.values()))
                )
                for category in stats:
                    pairs[i][category] = curses.color_pair(gui_util.color_scale(
                        *wb[i], math.sqrt(stats[category][i]), True
                    ))
            for i in (2,):
                wb[i] = (
                    max(val[i] for val in stats.values()),
                    min(val[i] for val in stats.values())
                )
                for category in stats:
                    pairs[i][category] = curses.color_pair(gui_util.color_scale(
                        *wb[i], stats[category][i], True
                    ))
            for i in (3,):
                wb[i] = (
                    math.sqrt(max(stats[cat][i] for cat in stats if cat)),
                    math.sqrt(min(val[i] for val in stats.values()))
                )
                for category in stats:
                    pairs[i][category] = curses.color_pair(gui_util.color_scale(
                        *wb[i], math.sqrt(stats[category][i]), True
                    ))
            ms = stats[""][2]
            wpm = int(24000/ms)

            # printing
            gui_util.insert_line_bottom(f"\nLayout: {target_layout}", right_pane)
            gui_util.insert_line_bottom(
                f"Overall {ms:.1f} ms per trigram ({wpm} wpm)\n", right_pane)
            header_line = (
                    "Category                     freq    exact   avg_ms      ms")
            gui_util.insert_line_bottom(header_line, right_pane)
            right_pane.scroll(len(stats))
            ymax = right_pane.getmaxyx()[0]
            row = ymax - len(stats)

            for category in sorted(stats):
                category_name = (category_display_names[category] 
                    if category in category_display_names else category)
                pad_char = " "
                if category.endswith(".") or not category:
                    category_name += " (total) "
                    pad_char = "-"
                if not category.startswith("."):
                    if "." not in category_name:
                        pad_char = "-"
                        category_name += " "
                right_pane.addstr( # category name
                    row, 0, ("{:" + pad_char + "<26}").format(category_name))
                right_pane.addstr( # freq
                    row, 27, f"{stats[category][0]:>6.2%}",
                    pairs[0][category])
                right_pane.addstr( # known_freq
                    row, 36, f"{stats[category][1]:>6.2%}",
                    pairs[1][category])
                right_pane.addstr( # speed
                    row, 45, f"{stats[category][2]:>6.1f}",
                    pairs[2][category])
                right_pane.addstr( # contrib
                    row, 53, f"{stats[category][3]:>6.2f}",
                    pairs[3][category])
                row += 1
            
            right_pane.refresh()
        elif command in ("r", "rank"):
            message("Layout ranking is not yet implemented", gui_util.red)
        elif command in ("bs", "bistrokes"):
            if not args:
                message("Crunching the numbers >>>", gui_util.green)
                message_win.refresh()
                right_pane.clear()
                data = bistroke_category_data(get_medians_for_layout(
                    load_csv_data(active_speeds_file), active_layout))
                print_stroke_categories(data)
            else:
                message("Individual bistroke stats are"
                    " not yet implemented", gui_util.red)
        elif command in ("ts", "tristroke"):
            if not args:
                message("Crunching the numbers >>>", gui_util.green)
                right_pane.clear()
                data = tristroke_category_data(get_medians_for_layout(
                    load_csv_data(active_speeds_file), active_layout))
                header_line = (
                    "Category                       ms    n     possible")
                gui_util.insert_line_bottom(header_line, right_pane)
                active_layout.preprocessors["counts"].join()
                print_stroke_categories(data, active_layout.counts)
            else:
                message("Individual tristroke stats are"
                    " not yet implemented", gui_util.red)
        elif command == "sf":
            if not args:
                active_speeds_file = "default"
            else:
                active_speeds_file = " ".join(args)
            message(f"Set active speeds file to {active_speeds_file}",
                    gui_util.green)
            if not os.path.exists("data/" + active_speeds_file + ".csv"):
                message("The new file will be written upon save", gui_util.blue)
            save_session_settings()
        elif command in ("h", "help"):
            help_text = [
                "",
                "",
                "Command <required thing> [optional thing]",
                "-----------------------------------------",
                "h[elp]: Show this list",
                "t[ype] <trigram>: Enter typing test",
                "l[ayout] [layout name]: Set active layout, or show options",
                "sf [filename]: Set or reset active speeds file",
                "s[ave]: Save tristroke data to active speeds file",
                "a[nalyze] [layout name]: Detailed layout analysis",
                "r[ank]: Rank all layouts",
                "bs [bistroke]: Show specified/all bistroke stats",
                "ts [tristroke]: Show specified/all tristroke stats",
                "tsc [category]: Show tristroke category/total stats",
                "q[uit]"
            ]
            ymax = right_pane.getmaxyx()[0]
            for line in help_text:
                if ":" in line:
                    white_part, rest = line.split(":", 1)
                    white_part += ":"
                    rest_pos = len(white_part)
                    right_pane.addstr(ymax-1, 0, white_part)
                    right_pane.addstr(ymax-1, rest_pos, rest, 
                                      curses.color_pair(gui_util.blue))
                else:
                    right_pane.addstr(ymax-1, 0, line)
                right_pane.scroll(1)
            right_pane.refresh()
        elif command in ("tsc",):
            if not args:
                category_name = ""
            else:
                category_name = args[0].lower().strip()

            if "(" in category_name:
                category_name = category_name[:category_name.find("(")].strip()
                # )) missing parentheses for rainbow brackets extension lmao
            if category_name in all_tristroke_categories:
                category = category_name
            elif category_name in category_display_names.values():
                for cat in category_display_names:
                    if category_display_names[cat] == category_name:
                        category = cat
                        break
            else:
                message("Unrecognized category", gui_util.red)
                continue
            
            message("Crunching the numbers >>>", gui_util.green)
            (speed, num_samples, with_fingers, without_fingers
            ) = data_for_tristroke_category(category, get_medians_for_layout(
                load_csv_data(active_speeds_file), active_layout
            ))
            display_name = (category_display_names[category] 
                if category in category_display_names else category)
            row = right_pane.getmaxyx()[0] - 18
            lh_fingers = tuple(
                finger.name for finger in reversed(sorted(Finger)) if finger < 0)
            rh_fingers = tuple(
                finger.name for finger in sorted(Finger) if finger > 0)
            spacing = 5
            indent = 17
            lh_fingers_label = " " * indent + (" " * spacing).join(lh_fingers)
            rh_fingers_label = " " * indent + (" " * spacing).join(rh_fingers)
            dash = "-" * len(lh_fingers_label)
            speeds_label = "speeds (ms): "
            n_label =  "       n = : "

            gui_util.insert_line_bottom(
                ("\nTristroke category: {}\nAverage ""{:.2f} ms, n={}")
                    .format(display_name, speed, num_samples),
                right_pane)
            
            for withname in ("\nWith finger:", "\nWithout finger:"):
                gui_util.insert_line_bottom(withname + "\n" + dash, right_pane)
                for label in (lh_fingers_label, rh_fingers_label):
                    gui_util.insert_line_bottom(
                        "\n".join((
                            label, speeds_label, n_label, dash
                        )),
                    right_pane)

            for data in (with_fingers, without_fingers):
                speeds = tuple(data[finger][0] for finger in list(Finger))
                ns = tuple(data[finger][1] for finger in list(Finger))
                sworst = max(speeds)
                sbest = min(filter(None, speeds))
                nworst = min(ns)
                nbest = max(ns)
                    
                for finglist in (lh_fingers, rh_fingers):
                    col = len(speeds_label)
                    for finger in finglist:
                        right_pane.addstr(
                            row, col, "{:>6.1f}".format(
                                data[Finger[finger]][0]),
                            curses.color_pair(gui_util.color_scale(
                                sworst, sbest, data[Finger[finger]][0], True)))
                        right_pane.addstr(
                            row+1, col, "{:>6}".format(
                                data[Finger[finger]][1]),
                            curses.color_pair(gui_util.color_scale(
                                nworst, nbest, data[Finger[finger]][1])))
                        col += 7
                    row += 4
                row += 3
            
            right_pane.refresh()
            input_win.move(0,0)
        # Debug commands
        elif command == "debug":
            gui_util.debug_win(message_win, "message_win")
            gui_util.debug_win(right_pane, "right_pane")
        elif command == "colors":
            message("COLORS: {}".format(curses.COLORS))
            message("COLOR_PAIRS: {}".format(curses.COLOR_PAIRS))
            ymax = right_pane.getmaxyx()[0]
            for i in range(curses.COLOR_PAIRS):
                right_pane.addstr(
                    i % ymax, 9*int(i/ymax), 
                    "Color {}".format(i), curses.color_pair(i))
            right_pane.refresh()
        elif command == "gradient":
            for i, color in enumerate(gui_util.gradient_colors):
                message("Gradient level {}".format(i), color)
        
        else:
            message("Unrecognized command", gui_util.red)            

def start_csv_row(tristroke: Tristroke):
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
    if not os.path.exists("data/" + filename + ".csv"):
        return data

    with open("data/" + filename + ".csv", "r", newline="") as csvfile:
        reader = csv.DictReader(csvfile, restkey="speeds")
        for row in reader:
            fingers = tuple(
                (Finger[row["finger" + str(n)]] for n in range(3)))
            coords = tuple(
                (Coord(float(row["x" + str(n)]), 
                       float(row["y" + str(n)])) for n in range(3)))
            tristroke = Tristroke(row["note"], fingers, coords)
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
    and obtain speeds_01, speeds_12, and speeds_02 as medians per tristroke.
    
    Returns a dict[Tristroke, (float, float, float)]"""
    by_fingers = {} # dict[Finger, list[Tristroke]]
    speeds = {} # dict[Tristroke, (list[float], list[float])]
    medians = {}
    for csv_tristroke in csv_data:
        if csv_tristroke.fingers not in by_fingers:
            by_fingers[csv_tristroke.fingers] = tuple(
                layout.nstrokes_with_fingers(csv_tristroke.fingers))
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
    total = [] # list[median]
    for tristroke in medians:
        for indices in ((0, 1), (1, 2)):
            data = medians[tristroke][indices[0]]
            total.append(data)
            category = bistroke_category(tristroke, *indices)
            try:
                known_medians[category].append(data)
            except KeyError:
                known_medians[category] = [data]
    
    # now estimate missing data
    all_medians = {} # dict[category, list[median]]
    is_estimate = {} # dict[category, bool]
    
    for category in all_bistroke_categories: # sorted general -> specific
        if category in known_medians:
            all_medians[category] = known_medians[category]
            is_estimate[category] = False
        else:
            is_estimate[category] = True
            if not category:
                is_estimate[category] = total
            all_medians[category] = []
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
                
def tristroke_category_data(medians: dict):
    """Returns a 
    dict[category: string, (speed: float, num_samples: int)]
    where num_samples is the number of unique bistroke/tristroke median 
    speeds that have been combined to obtain the speed stat. num_samples 
    is positive if speed is obtained from known data, and negative if speed 
    is estimated from related data, which occurs if no known data is 
    directly applicable.
    
    Note that medians is the output of get_medians_for_layout()."""
    known_medians = {} # dict[category, list[median]]
    total = [] # list[median]
    for tristroke in medians:
        data = medians[tristroke][2]
        total.append(data)
        category = tristroke_category(tristroke)
        try:
            known_medians[category].append(data)
        except KeyError:
            known_medians[category] = [data]
        
    # now estimate missing data
    all_medians = {} # dict[category, list[median]]
    is_estimate = {} # dict[category, bool]

    all_categories = all_tristroke_categories.copy()

    # Initial transfer
    for category in all_categories: # sorted general -> specific
        is_estimate[category] = False
        if category in known_medians:
            all_medians[category] = known_medians[category]
        else: # fill in from subcategories
            if not category:
                all_medians[category] = total
                continue
            all_medians[category] = []
            if category.startswith("."):
                for instance in known_medians:
                    if instance.endswith(category):
                        all_medians[category].extend(known_medians[instance])
            else:
                if not category.endswith("."):
                    is_estimate[category] = True
                for subcategory in known_medians:
                    if subcategory.startswith(category):
                        all_medians[category].extend(known_medians[subcategory])
            # There may be no subcategories with known data either. 
            # Hence the next stages
    
    # Build up some stuff from trigrams
    # if not all_medians["sfb"]:
    #     for tristroke in medians:
    #         if tristroke_category(tristroke).startswith("sfs"):
    #             all_medians["sfb"].append(medians[tristroke][2])
    
    # fill in from supercategory
    all_categories.reverse() # most specific first
    for category in all_categories:
        if not all_medians[category] and not category.startswith("."):
            for supercategory in all_categories:
                if (category.startswith(supercategory) and 
                        bool(all_medians[supercategory]) and
                        category != supercategory):
                    all_medians[category] = all_medians[supercategory]
                    break
    # fill in scissors from subcategories
    for category in all_categories:
        if not all_medians[category] and category.startswith("."):
            is_estimate[category] = True # the subcategory is an estimate
            for instance in all_categories:
                if (instance.endswith(category) and instance != category):
                    all_medians[category].extend(all_medians[instance])
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

def data_for_tristroke_category(category: str, medians: dict):
    """Returns (speed: float, num_samples: int, 
    with_fingers: dict[Finger, (speed: float, num_samples: int)],
    without_fingers: dict[Finger, (speed: float, num_samples: int)])
    for the given tristroke category.

    Note that medians is the output of get_medians_for_layout()."""

    all_samples = []
    speeds_with_fingers = {finger: [] for finger in list(Finger)}
    speeds_without_fingers = {finger: [] for finger in list(Finger)}

    applicable = applicable_function(category)

    for tristroke in medians:
        cat = tristroke_category(tristroke)
        if not applicable(cat):
            continue
        speed = medians[tristroke][2]
        used_fingers = {finger for finger in tristroke.fingers}
        all_samples.append(speed)
        for finger in list(Finger):
            if finger in used_fingers:
                speeds_with_fingers[finger].append(speed)
            else:
                speeds_without_fingers[finger].append(speed)
    
    num_samples = len(all_samples)
    speed = statistics.mean(all_samples) if num_samples else 0
    with_fingers = {}
    without_fingers = {}
    for speeds_l, output_l in zip(
            (speeds_with_fingers, speeds_without_fingers),
            (with_fingers, without_fingers)):
        for finger in list(Finger):
            n = len(speeds_l[finger])
            speed = statistics.mean(speeds_l[finger]) if n else 0
            output_l[finger] = (speed, n)
    
    return (speed, num_samples, with_fingers, without_fingers)

def analyze_layout(layout: layout.Layout, tricatdata: dict, medians: dict):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    tricatdata is the output of tristroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]
    
    medians is the output of get_medians_for_layout(). That is, 
    dict[Tristroke, (float, float, float)]"""
    with open("data/shai.json") as file:
        corpus = json.load(file)

    trigram_freqs = corpus["trigrams"]
    # {category: [total_time, exact_freq, total_freq]}
    by_category = {category: [0,0,0] for category in all_tristroke_categories}
    for trigram in trigram_freqs:
        try:
            tristroke = layout.to_nstroke(trigram)
        except KeyError: # contains key not in layout
            continue
        cat = tristroke_category(tristroke)
        freq = trigram_freqs[trigram]
        try:
            speed = medians[tristroke][2]
            by_category[cat][1] += freq
        except KeyError: # no entry in known medians
            speed = tricatdata[cat][0]
        finally:
            by_category[cat][0] += speed * freq
            by_category[cat][2] += freq
    
    # fill in sum categories
    for cat in all_tristroke_categories:
        if not by_category[cat][2]:
            applicable = applicable_function(cat)
            for othercat in all_tristroke_categories:
                if by_category[othercat][2] and applicable(othercat):
                    for i in range(3):
                        by_category[cat][i] += by_category[othercat][i]

    total_freq = by_category[""][2]
    if not total_freq:
        total_freq = 1
    stats = {}
    for cat in all_tristroke_categories:
        cat_freq = by_category[cat][2]
        if not cat_freq:
            cat_freq = 1
        freq_prop = by_category[cat][2] / total_freq
        known_prop = by_category[cat][1] / cat_freq
        cat_speed = by_category[cat][0] / cat_freq
        contribution = by_category[cat][0] / total_freq
        stats[cat] = (freq_prop, known_prop, cat_speed, contribution)
    
    return stats

def analyze_layout_nodetail(layout: layout.Layout, 
                            tricatdata: dict, medians: dict):
    """Like analyze_layout but instead of breaking down by category, only
    calculates stats for the "total" category.
    
    Returns (speed, known_prop)"""
    with open("/data/shai.json") as file:
        corpus = json.load(file)

    trigram_freqs = corpus["trigrams"]
    total_freq = 0
    known_freq = 0
    total_time = 0
    for trigram in trigram_freqs:
        try:
            tristroke = layout.to_nstroke(trigram)
        except KeyError: # contains key not in layout
            continue
        freq = trigram_freqs[trigram]
        try:
            speed = medians[tristroke][2]
            known_freq += freq
        except KeyError: # no entry in known medians
            speed = tricatdata[tristroke_category(tristroke)][0]
        finally:
            total_time += speed
            total_freq += freq

    return (total_time/total_freq, known_freq/total_freq)
    
if __name__ == "__main__":
    curses.wrapper(main)