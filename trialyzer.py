from calendar import leapdays
import csv
import itertools
import multiprocessing
import operator
import statistics
import os
import math
import json
from typing import Iterable

from board import Coord
from fingermap import Finger
from nstroke import *
import typingtest
import curses
import curses.textpad
import layout
import gui_util

def main(stdscr: curses.window):
    
    startup_messages = []
    
    try:
        with open("session_settings.json") as settings_file:
            settings = json.load(settings_file)
        some_default = False
        try:
            analysis_target = layout.get_layout(settings["analysis_target"])
        except (OSError, KeyError):
            analysis_target = layout.get_layout("qwerty")
            some_default = True
        try:
            user_layout = layout.get_layout(settings["user_layout"])
        except (OSError, KeyError):
            user_layout = layout.get_layout("qwerty")
            some_default = True
        try:
            active_speeds_file = settings["active_speeds_file"]
        except KeyError:
            active_speeds_file = "default"
            some_default = True
        try:
            trigram_precision = int(settings["trigram_precision"])
        except (KeyError, ValueError):
            trigram_precision = 500
            some_default = True
        startup_messages.append(("Loaded user settings", gui_util.green))
        if some_default:
            startup_messages.append((
                "Set some missing/bad settings to default", gui_util.blue))
    except (OSError, KeyError):
        active_speeds_file = "default"
        analysis_target = layout.get_layout("qwerty")
        user_layout = layout.get_layout("qwerty")
        trigram_precision = 500
        startup_messages.append(("Using default user settings", gui_util.red))

    def load_trigrams(trigram_precision: int):
        with open("data/shai.json") as file:
            corpus = json.load(file)
        trigram_list = corpus["toptrigrams"]
        if trigram_precision <= 0 or trigram_precision >= len(trigram_list):
            trigram_precision = len(trigram_list)
        trigram_freqs = dict()
        included = 0
        total = 0
        for i, item in enumerate(trigram_list):
            if i < trigram_precision:
                trigram_freqs[item["Ngram"]] = item["Count"]
                included += item["Count"]
            total += item["Count"]

        return trigram_freqs, included/total
    
    def save_session_settings():
        with open("session_settings.json", "w") as settings_file:
            json.dump(
                {   "analysis_target": analysis_target.name,
                    "user_layout": user_layout.name,
                    "active_speeds_file": active_speeds_file,
                    "trigram_precision": trigram_precision,
                }, settings_file)

    trigram_freqs, trigram_percent = load_trigrams(trigram_precision)
    save_session_settings()
    
    def header_text(): 
        if trigram_precision:
            precision_text = f"{trigram_precision} most frequent"
        else:
            precision_text = "all"
        return [
            "\"h\" or \"help\" to show command list",
            f"Analysis target: {analysis_target}",
            f"User layout: {user_layout}",
            f"Active speeds file: {active_speeds_file}"
            f" (/data/{active_speeds_file}.csv)",
            f"Trigrams used: {precision_text} ({trigram_percent:.3%})"
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
    startup_lines = len(header_text())
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
    
    typingtest_data = []
    
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

    def print_analysis_stats(stats: dict, header_line: str):
        # colors
        col_settings = (
            {"transform": math.sqrt, 
                "scale_filter": lambda val: val != stats[""][0]},
            {"transform": math.sqrt},
            {"worst": max, "best": min},
            {"transform": math.sqrt, "worst": max, "best": min,
                "scale_filter": lambda val: val != stats[""][3]},
         )
        pairs = gui_util.apply_scales(stats, col_settings)

        gui_util.insert_line_bottom(header_line, right_pane)
        right_pane.scroll(len(stats))
        ymax = right_pane.getmaxyx()[0]
        row = ymax - len(stats)

        # printing
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

    def scan_dir(path: str = "layouts/.", exclude: str = "."):
        file_list = []
        with os.scandir(path) as files:
            for file in files:
                if exclude not in file.name and file.is_file():
                    file_list.append(file.name)
        return file_list    

    def parse_category(user_input: str = ""):
        """Returns None and prints error message if category not found."""
        if not user_input:
                category_name = ""
        else:
            category_name = user_input.lower().strip()

        if "(" in category_name:
            category_name = category_name[:category_name.find("(")].strip()
            # )) missing parentheses for rainbow brackets extension lmao
        if category_name in all_tristroke_categories:
            return category_name
        elif category_name in category_display_names.values():
            for cat in category_display_names:
                if category_display_names[cat] == category_name:
                    return cat
        else:
            message("Unrecognized category", gui_util.red)
            return None     

    for item in startup_messages:
        message(*item)
    
    while True:
        for i in range(len(header_text())):
            content_win.move(i, 0)
            content_win.clrtoeol()
        content_win.addstr(0, 0, "\n".join(header_text()))
        content_win.addstr(height-2, 0, "> ")
        content_win.refresh()

        input_win.clear()
        input_win.refresh()

        args = get_input().split()
        if not len(args):
            continue
        command = args.pop(0).lower()

        if command in ("q", "quit"):
            return
        elif command in ("t", "type"):
            if not args: # autosuggest trigram
                # Choose the most frequent trigram from the least completed 
                # category of the analysis target layout
                with open("data/shai.json") as file:
                    corpus = json.load(file)
                trigram_list = corpus["toptrigrams"]
                medians = get_medians_for_layout(
                    load_csv_data(active_speeds_file), analysis_target)
                catdata = tristroke_category_data(medians)
                analysis_target.preprocessors["counts"].join()
                counts = analysis_target.counts
                completion = {}
                for cat in catdata:
                    if cat.startswith(".") or cat.endswith(".") or cat == "":
                        continue
                    n = catdata[cat][1]
                    completion[cat] = n/counts[cat] if n > 0 else 0

                ruled_out = {analysis_target.to_ngram(tristroke)
                    for tristroke in medians} # already have data
                trigram = None

                def find_from_best_cat():
                    if not completion:
                        return None
                    best_cat = min(completion, key = lambda cat: completion[cat])
                    # trigram_list is sorted by descending frequency
                    for entry in trigram_list:
                        ng = tuple(key for key in entry["Ngram"])
                        if ng in ruled_out:
                            continue
                        try:
                            tristroke = analysis_target.to_nstroke(ng)
                        except KeyError: # contains key not in layout
                            continue
                        if tristroke_category(tristroke) == best_cat:
                            ruled_out.add(ng)
                            if user_layout.to_ngram(tristroke): # keys exist
                                return tristroke
                    # if we get to this point, 
                    # there was no compatible trigram in the category
                    # Check next best category
                    del completion[best_cat]
                    return find_from_best_cat()
                
                tristroke = find_from_best_cat()
                trigram = user_layout.to_ngram(tristroke)
                if not tristroke:
                    message("Unable to autosuggest - all compatible trigrams"
                        " between the user layout and analysis target"
                        " already have data", gui_util.red)
                    continue
                else:
                    fingers = tuple(finger.name for finger in tristroke.fingers)
                    message(f"Autosuggesting trigram {' '.join(trigram)}\n"
                        f"({analysis_target.name} "
                        f"{' '.join(analysis_target.to_ngram(tristroke))})\n"
                        "Be sure to use {} {} {}".format(*fingers),
                        gui_util.blue)
            elif len(args) == 3:
                tristroke = user_layout.to_nstroke(args)
            elif len(args) == 1 and len(args[0]) == 3:
                tristroke = user_layout.to_nstroke(args[0])
            else:
                message("Malformed trigram", gui_util.red)
                continue
            csvdata = load_csv_data(active_speeds_file)
            if tristroke in csvdata:
                message(
                    f"Note: this tristroke already has "
                    f"{len(csvdata[tristroke][0])} data points",
                    gui_util.blue)
            message("Starting typing test >>>", gui_util.green)
            typingtest.test(right_pane, tristroke, user_layout, csvdata)
            input_win.clear()
            save_csv_data(csvdata, active_speeds_file)
            message("Typing data saved", gui_util.green)
        elif command in ("c", "clear"):
            if len(args) == 3:
                trigram = tuple(args)
            elif len(args) == 1 and len(args[0]) == 3:
                trigram = args[0]
            else:
                message("Usage: c[lear] <trigram>", gui_util.red)
                continue
            csvdata = load_csv_data(active_speeds_file)
            tristroke = user_layout.to_nstroke(trigram)
            try:
                num_deleted = len(csvdata.pop(tristroke)[0])
            except KeyError:
                num_deleted = 0
            save_csv_data(csvdata, active_speeds_file)
            message(f"Deleted {num_deleted} data points for {' '.join(trigram)}")
        elif command == "target":
            layout_name = " ".join(args)
            if layout_name: # set layout
                try:
                    analysis_target = layout.get_layout(layout_name)
                    message("Set " + layout_name + " as the analysis target.",
                            gui_util.green)
                    save_session_settings()
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
            else:
                message("Usage: target <layout name>", gui_util.red)
        elif command in ("l", "layout"):
            layout_name = " ".join(args)
            if layout_name:
                try:
                    message("\n"+ layout_name + "\n"
                         + repr(layout.get_layout(layout_name)), win=right_pane)
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
            else:
                message("\n" + analysis_target.name + "\n"
                     + repr(analysis_target), win=right_pane)
        elif command in ("u", "use"):
            layout_name = " ".join(args)
            if layout_name: # set layout
                try:
                    user_layout = layout.get_layout(layout_name)
                    message("Set " + layout_name + " as the user layout.",
                            gui_util.green)
                    save_session_settings()
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
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
                target_layout = analysis_target
            message("Crunching the numbers >>>", gui_util.green)
            message_win.refresh()
            
            medians = get_medians_for_layout(
                load_csv_data(active_speeds_file), target_layout)
            tri_stats = tristroke_analysis(
                target_layout, tristroke_category_data(medians), 
                medians, trigram_freqs)
            bi_stats = bistroke_analysis(
                target_layout, bistroke_category_data(medians), medians)
            
            tri_ms = tri_stats[""][2]
            tri_wpm = int(24000/tri_ms)
            bi_ms = bi_stats[""][2]
            bi_wpm = int(12000/bi_ms)

            gui_util.insert_line_bottom(f"\nLayout: {target_layout}", right_pane)
            gui_util.insert_line_bottom(
                f"Overall {tri_ms:.1f} ms per trigram ({tri_wpm} wpm)", right_pane)
            gui_util.insert_line_bottom(
                f"Overall {bi_ms:.1f} ms per bigram ({bi_wpm} wpm)", right_pane)
            
            tri_header_line = (
                "\nTristroke categories         freq    exact   avg_ms      ms")
            bi_header_line = (
                "\nBistroke categories          freq    exact   avg_ms      ms")
            print_analysis_stats(tri_stats, tri_header_line)
            print_analysis_stats(bi_stats, bi_header_line)
        elif command in ("r", "rank"): # uses summary_tristroke_analysis()
            layout_file_list = scan_dir()
            if not layout_file_list:
                message("No layouts found in /layouts/", gui_util.red)
                continue
            message(f"Analyzing {len(layout_file_list)} layouts >>>", gui_util.green)
            layouts = [layout.get_layout(name) for name in layout_file_list]
            data = {}
            csvdata = load_csv_data(active_speeds_file)
            width = max(len(name) for name in layout_file_list)
            gui_util.insert_line_bottom(
                "\nLayout" + " "*(width-3) + "avg_ms   wpm    exact", right_pane)
            ymax = right_pane.getmaxyx()[0]
            first_row = ymax - len(layouts) - 2
            if first_row < 1:
                first_row = 1
            right_pane.scroll(min(ymax-1, len(layouts) + 2))

            col_settings = (
                {"transform": math.sqrt, "worst": max, "best": min}, # avg_ms
                {"transform": math.sqrt}, # exact
            )

            num_displayed = ymax - first_row

            for lay in layouts:
                medians = get_medians_for_layout(csvdata, lay)
                tricatdata = tristroke_category_data(medians)
                data[lay.name] = summary_tristroke_analysis(
                    lay, tricatdata, medians, trigram_freqs)
                row = first_row
                sorted_ = list(sorted(data, key=lambda d: data[d][0]))
                displayed = {sorted_[i]: data[sorted_[i]] 
                    for i in range(len(sorted_)) if i < num_displayed}
                pairs = gui_util.apply_scales(displayed, col_settings)
                for lay in sorted_:
                    try:
                        right_pane.move(row, 0)
                        right_pane.clrtoeol()
                        right_pane.addstr(
                            row, 0, f"{lay:{width}s}")
                        right_pane.addstr( # avg_ms
                            row, width+3, f"{data[lay][0]:6.2f}",
                            pairs[0][lay])
                        right_pane.addstr( # wpm
                            row, width+12, f"{int(24000/data[lay][0]):3}",
                            pairs[0][lay])
                        right_pane.addstr( # exact
                            row, width+18, f"{data[lay][1]:6.2%}",
                            pairs[1][lay])
                        row += 1
                    except curses.error:
                        continue # list went off the screen
                        # TODO something better than just 
                        # cutting off the list like this lmao
                right_pane.refresh()
            message(f"Ranking complete", gui_util.green)
        elif command == "rt": # uses full tristroke_analysis()
            reverse_opts = {"min": False, "max": True}
            analysis_opts = {"freq": 0, "exact": 1, "avg_ms": 2, "ms": 3}
            try:
                reverse_ = reverse_opts[args[0]]
                sorting_col = analysis_opts[args[1]]
            except (KeyError, IndexError):
                message("Usage: rt <min|max> <freq|exact|avg_ms|ms> [category]",
                    gui_util.red)
                continue
            try:
                category = parse_category(args[2])
                if category is None:
                    continue
            except IndexError:
                category = ""
            category_name = (category_display_names[category] 
                if category in category_display_names else category)
            if category.endswith(".") or not category:
                category_name += " (total) "

            layout_file_list = scan_dir()
            if not layout_file_list:
                message("No layouts found in /layouts/", gui_util.red)
                continue
            message(f"Analyzing {len(layout_file_list)} layouts >>>",
                gui_util.green)
            width = max(len(name) for name in layout_file_list)
            gui_util.insert_line_bottom(
                f"\nRanking by tristroke category: {category_name}, "
                f"{args[0]} {args[1]} first"
                "\nLayout" + " "*(width-1) 
                + "freq    exact   avg_ms      ms", right_pane)
            ymax = right_pane.getmaxyx()[0]
            first_row = ymax - len(layout_file_list) - 3
            if first_row < 2:
                first_row = 2
            right_pane.scroll(min(ymax-2, len(layout_file_list) + 1))
            right_pane.refresh()
            layouts = [layout.get_layout(name) for name in layout_file_list]
            num_displayed = ymax - first_row

            data = {}
            csvdata = load_csv_data(active_speeds_file)

            col_settings = [ # for colors
                {"transform": math.sqrt}, # freq
                {"transform": math.sqrt}, # exact
                {"worst": max, "best": min}, # avg_ms
                {"transform": math.sqrt, "worst": max, "best": min}, # ms
            ]
            col_settings_inverted = col_settings.copy()
            col_settings_inverted[0] = col_settings_inverted[3]
            
            for lay in layouts:
                medians = get_medians_for_layout(csvdata, lay)
                tricatdata = tristroke_category_data(medians)
                data[lay.name] = tristroke_analysis(
                    lay, tricatdata, medians, trigram_freqs)
                row = first_row
                
                # color freq by whether the category is faster than total
                try:
                    this_avg = statistics.mean(
                        data[layname][category][2] for layname in data)
                    total_avg = statistics.mean(
                        data[layname][""][2] for layname in data)
                    invert = this_avg > total_avg
                except statistics.StatisticsError:
                    invert = False
                names = list(sorted(
                    data, key=lambda name: data[name][category][sorting_col], 
                    reverse=reverse_))
                rows = {name: data[name][category] 
                    for i, name in enumerate(names) if i < num_displayed}
                if invert:
                    pairs = gui_util.apply_scales(
                        rows, col_settings_inverted)    
                else:
                    pairs = gui_util.apply_scales(rows, col_settings)

                # printing
                for rowname in rows:
                    try:
                        right_pane.move(row, 0)
                        right_pane.clrtoeol()
                        right_pane.addstr(
                            row, 0, f"{rowname:{width}s}   ")
                        right_pane.addstr( # freq
                            row, width+3, f"{rows[rowname][0]:>6.2%}",
                            pairs[0][rowname])
                        right_pane.addstr( # exact
                            row, width+12, f"{rows[rowname][1]:>6.2%}",
                            pairs[1][rowname])
                        right_pane.addstr( # avg_ms
                            row, width+21, f"{rows[rowname][2]:>6.1f}",
                            pairs[2][rowname])
                        right_pane.addstr( # ms
                            row, width+29, f"{rows[rowname][3]:>6.2f}",
                            pairs[3][rowname])
                        row += 1
                    except curses.error:
                        continue # list went off the screen
                        # TODO something better than just 
                        # cutting off the list like this lmao
                right_pane.refresh()
            message(f"Ranking complete", gui_util.green)
        elif command in ("bs", "bistroke"):
            if not args:
                message("Crunching the numbers >>>", gui_util.green)
                message_win.refresh()
                right_pane.clear()
                data = bistroke_category_data(get_medians_for_layout(
                    load_csv_data(active_speeds_file), analysis_target))
                print_stroke_categories(data)
            else:
                message("Individual bistroke stats are"
                    " not yet implemented", gui_util.red)
        elif command in ("ts", "tristroke"):
            if not args:
                message("Crunching the numbers >>>", gui_util.green)
                right_pane.clear()
                data = tristroke_category_data(get_medians_for_layout(
                    load_csv_data(active_speeds_file), analysis_target))
                header_line = (
                    "Category                       ms    n     possible")
                gui_util.insert_line_bottom(header_line, right_pane)
                analysis_target.preprocessors["counts"].join()
                print_stroke_categories(data, analysis_target.counts)
            else:
                message("Individual tristroke stats are"
                    " not yet implemented", gui_util.red)
        elif command == "df":
            if not args:
                active_speeds_file = "default"
            else:
                active_speeds_file = " ".join(args)
            message(f"Set active speeds file to /data/{active_speeds_file}.csv",
                    gui_util.green)
            if not os.path.exists(f"data/{active_speeds_file}.csv"):
                message("The new file will be written upon save", gui_util.blue)
            save_session_settings()
        elif command in ("i", "improve"):
            pins = []
            if "pin" in args:
                while True:
                    token = args.pop()
                    if token == "pin":
                        break
                    else:
                        pins.append(token)
            if args:
                layout_name = " ".join(args)
                try:
                    target_layout = layout.get_layout(layout_name)
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
                    continue
            else:
                target_layout = analysis_target
            message("Using steepest ascent... >>>", gui_util.green)
            
            medians = get_medians_for_layout(
                load_csv_data(active_speeds_file), target_layout)
            tricatdata = tristroke_category_data(medians)

            initial_score = summary_tristroke_analysis(
                target_layout, tricatdata, medians, trigram_freqs)[0]
            message(f"\nInitial layout: avg_ms = {initial_score:.4f}\n"
                + repr(target_layout), win=right_pane)
            
            num_swaps = 0
            optimized = target_layout
            for optimized, score, swap in steepest_ascent(
                    target_layout, tricatdata, medians, trigram_freqs, pins):
                num_swaps += 1
                repr_ = repr(optimized)
                message(f"Swap #{num_swaps} ({swap[0]} {swap[1]}) results "
                    f"in avg_ms = {score:.4f}\n"
                    + repr_, win=right_pane)
            message(f"Local optimum reached", gui_util.green, right_pane)
            
            if optimized is not target_layout:
                with open(f"layouts/{optimized.name}", "w") as file:
                        file.write(repr_)
                message(
                    f"Saved new layout as {optimized.name}",
                    gui_util.green, right_pane)
        elif command == "precision":
            try:
                trigram_precision = int(args[0])
            except IndexError:
                message("Usage: precision <n>\nOr use \"precision full\"",
                    gui_util.red)
                continue
            except ValueError:
                if args[0] == "full":
                    trigram_precision = 0
                else:
                    message("Precision must be an integer", gui_util.red)
                    continue
            trigram_freqs, trigram_percent = load_trigrams(trigram_precision)
            save_session_settings()
            message(f"Set trigram precision to {args[0]} ({trigram_percent:.3%})", 
                gui_util.green)
        elif command in ("h", "help"):
            help_text = [
                "",
                "",
                "Command <required thing> [optional thing] option1|option2",
                "------General commands------",
                "h[elp]: Show this list",
                "reload [layout name]: Reload layout(s) from files",
                "precision <n|full>: Analyze using the top n trigrams, or all",
                "l[ayout] [layout name]: View layout",
                "q[uit]",
                "----Typing data commands----",
                "u[se] <layout name>: Set layout used in typing test",
                "t[ype] [trigram]: Run typing test",
                "c[lear] <trigram>: Erase data for trigram",
                "df [filename]: Set typing data file, or use default",
                "-----Analysis commands-----",
                "target <layout name>: Set analysis target",
                "a[nalyze] [layout name]: Detailed layout analysis",
                "r[ank]: Rank all layouts by wpm",
                "rt <min|max> <freq|exact|avg_ms|ms> [category]: "
                    "Rank by tristroke statistic",
                "bs [bistroke]: Show specified/all bistroke stats",
                "ts [tristroke]: Show specified/all tristroke stats",
                "tsc [category]: Show tristroke category/total stats",
                "i[mprove] [layout name] [pin <keys>]: Optimize layout"
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
                category = ""
            else:
                category = parse_category(args[0])
                if category is None:
                    continue
            
            message("Crunching the numbers >>>", gui_util.green)
            (speed, num_samples, with_fingers, without_fingers
            ) = data_for_tristroke_category(category, get_medians_for_layout(
                load_csv_data(active_speeds_file), analysis_target
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
                nworst = min(filter(None, ns))
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
                                nworst, nbest, data[Finger[finger]][1], True)))
                        col += 7
                    row += 4
                row += 3
            
            right_pane.refresh()
            input_win.move(0,0)
        elif command == "reload":
            if args:
                layout_name = " ".join(args)
                try:
                    layout.Layout.loaded[layout_name] = layout.Layout(
                        layout_name)
                    message(f"Reloaded {layout_name} >>>", gui_util.green)
                    message(f"\n{layout_name}\n"
                        + repr(layout.get_layout(layout_name)),
                        win=right_pane)
                except OSError:
                    message(f"/layouts/{layout_name} was not found.", 
                            gui_util.red)
                    continue
            else:
                for layout_name in layout.Layout.loaded:
                    try:
                        layout.Layout.loaded[layout_name] = layout.Layout(
                            layout_name)
                    except OSError:
                        del layout.Layout.loaded[layout_name]
                message("Reloaded all layouts", gui_util.green)
            # If either of these were deleted just let it crash lol
            # too lazy to deal with that
            user_layout = layout.get_layout(user_layout.name)
            analysis_target = layout.get_layout(analysis_target.name)
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
            if "speeds" not in row:
                continue
            fingers = tuple(
                (Finger[row["finger" + str(n)]] for n in range(3)))
            coords = tuple(
                (Coord(float(row["x" + str(n)]), 
                       float(row["y" + str(n)])) for n in range(3)))
            tristroke = Tristroke(row["note"], fingers, coords)
            # there may be multiple rows for the same tristroke
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
                if not data[tristroke] or not data[tristroke][0]:
                    continue
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
                    speeds[layout_tristroke][0].extend(
                        csv_data[csv_tristroke][0])
                    speeds[layout_tristroke][1].extend(
                        csv_data[csv_tristroke][1])
    for tristroke in speeds:
        speeds_01 = speeds[tristroke][0]
        speeds_12 = speeds[tristroke][1]
        speeds_02 = map(operator.add, speeds_01, speeds_12)
        try:
            medians[tristroke] = (
                statistics.median(speeds_01),
                statistics.median(speeds_12),
                statistics.median(speeds_02)
            )
        except statistics.StatisticsError:
            continue
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
    
    all_categories = all_bistroke_categories.copy()


    for category in all_categories: # sorted general -> specific
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
    
    all_categories.reverse() # most specific first
    for category in all_categories:
        if not all_medians[category]: # data needed
            for supercategory in all_categories: # most specific first
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
    
    # Fill from other categories
    if not all_medians["sfb."]:
        for tristroke in medians:
            if tristroke_category(tristroke).startswith("sfr"):
                all_medians["sfb."].append(medians[tristroke][2])
    
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

def bistroke_analysis(layout: layout.Layout, bicatdata: dict, medians: dict):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    bicatdata is the output of bistroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]
    
    medians is the output of get_medians_for_layout(). That is, 
    dict[Tristroke, (float, float, float)]"""
    with open("data/shai.json") as file:
        corpus = json.load(file)

    # break medians down from tristrokes to bistrokes
    bi_medians = {}
    for tristroke in medians:
        bi0 = (
            Nstroke(
                tristroke.note, tristroke.fingers[:2], tristroke.coords[:2]),
            medians[tristroke][0])
        bi1 = (
            Nstroke(
                tristroke.note, tristroke.fingers[1:], tristroke.coords[1:]),
            medians[tristroke][1])
        for bi_tuple in (bi0, bi1):
            try:
                bi_medians[bi_tuple[0]].append(bi_tuple[1])
            except KeyError:
                bi_medians[bi_tuple[0]] = [bi_tuple[1]]
    for bistroke in bi_medians:
        bi_medians[bistroke] = statistics.mean(bi_medians[bistroke])
    
    bigram_freqs = corpus["bigrams"]
    # {category: [total_time, exact_freq, total_freq]}
    by_category = {category: [0,0,0] for category in all_bistroke_categories}
    for bigram in bigram_freqs:
        try:
            bistroke = layout.to_nstroke(bigram)
        except KeyError: # contains key not in layout
            continue
        cat = bistroke_category(bistroke)
        freq = bigram_freqs[bigram]
        try:
            speed = bi_medians[bistroke]
            by_category[cat][1] += freq
        except KeyError: # no entry in known medians
            speed = bicatdata[cat][0]
        finally:
            by_category[cat][0] += speed * freq
            by_category[cat][2] += freq
    
    # fill in sum categories
    for cat in all_bistroke_categories:
        if not by_category[cat][2]:
            applicable = applicable_function(cat)
            for othercat in all_bistroke_categories:
                if by_category[othercat][2] and applicable(othercat):
                    for i in range(3):
                        by_category[cat][i] += by_category[othercat][i]

    total_freq = by_category[""][2]
    if not total_freq:
        total_freq = 1
    stats = {}
    for cat in all_bistroke_categories:
        cat_freq = by_category[cat][2]
        if not cat_freq:
            cat_freq = 1
        freq_prop = by_category[cat][2] / total_freq
        known_prop = by_category[cat][1] / cat_freq
        cat_speed = by_category[cat][0] / cat_freq
        contribution = by_category[cat][0] / total_freq
        stats[cat] = (freq_prop, known_prop, cat_speed, contribution)
    
    return stats

def tristroke_analysis(layout: layout.Layout, tricatdata: dict, medians: dict,
    trigram_freqs: dict):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    tricatdata is the output of tristroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]
    
    medians is the output of get_medians_for_layout(). That is, 
    dict[Tristroke, (float, float, float)]"""
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

def summary_tristroke_analysis(
        layout: layout.Layout, tricatdata: dict, medians: dict, 
        trigram_freqs: dict):
    """Like tristroke_analysis but instead of breaking down by category, only
    calculates stats for the "total" category.
    
    Returns (speed, known_prop)"""

    total_freq, known_freq, total_time = raw_summary_tristroke_analysis(
        layout, tricatdata, medians, trigram_freqs)

    return (total_time/total_freq, known_freq/total_freq)

def raw_summary_tristroke_analysis(
        layout: layout.Layout, tricatdata: dict, 
        medians: dict, trigram_freqs: dict):
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
            total_time += speed * freq
            total_freq += freq
    return (total_freq, known_freq, total_time)

def steepest_ascent(layout_: layout.Layout, tricatdata: dict, medians: dict, 
        trigram_freqs: dict, pins: Iterable[str] = tuple()):
    lay = layout.Layout(layout_.name, False)
    lay.name += "-ascended"
    
    swappable = set(lay.keys.values())
    for key in pins:
        swappable.discard(key)

    total_freq, known_freq, total_time = raw_summary_tristroke_analysis(
        lay, tricatdata, medians, trigram_freqs
    )
    
    scores = [total_time/total_freq]
    with multiprocessing.Pool(4) as pool:
        while True:
            # best_swap = None
            # best_time = scores[-1]
            # best_data = (total_freq, known_freq, total_time)
            # for swap in itertools.combinations(lay.keys.values(), 2):
            #     data = swapped_score(swap, total_freq, known_freq, total_time)
            #     swapped_time = data[2]/data[0]
            #     if swapped_time < best_time:
            #         best_time = swapped_time
            #         best_swap = swap
            #         best_data = data
            swaps = itertools.combinations(swappable, 2)
            args = ((swap, total_freq, known_freq, total_time, lay,
                     trigram_freqs, medians, tricatdata) 
                for swap in swaps)
            datas = pool.starmap(swapped_score, args, 200)
            if not len(datas):
                return
            best = min(datas, key=lambda d: d[2]/d[0])
            best_swap = best[3]
            best_score = best[2]/best[0]

            if best_score < scores[-1]:
                total_freq, known_freq, total_time = best[:3]
                scores.append(best_score)
                lay.swap(best_swap)
                
                yield lay, scores[-1], best_swap
            else:
                return

def swapped_score(swap: tuple[str], total_freq, known_freq, total_time,
    lay: layout.Layout, trigram_freqs: dict, medians: dict, tricatdata: dict):
    # swaps should be length 2

    def swapped_ngram(ngram):
        swapped = []
        for key in ngram:
            if key == swap[0]:
                swapped.append(swap[1])
            elif key == swap[1]:
                swapped.append(swap[0])
            else:
                swapped.append(key)
        return tuple(swapped)
    
    for ngram in lay.ngrams_with_any_of(swap):
        try:
            freq = trigram_freqs["".join(ngram)]
        except KeyError: # contains key not in corpus
            continue
        
        tristroke = lay.to_nstroke(ngram)
        try:
            speed = medians[tristroke][2]
            known_freq -= freq
        except KeyError: # no entry in known medians
            speed = tricatdata[tristroke_category(tristroke)][0]
        finally:
            total_time -= speed * freq
            total_freq -= freq
        
        swapped_tristroke = lay.to_nstroke(swapped_ngram(ngram))
        try:
            speed = medians[swapped_tristroke][2]
            known_freq += freq
        except KeyError: # no entry in known medians
            speed = tricatdata[tristroke_category(swapped_tristroke)][0]
        finally:
            total_time += speed * freq
            total_freq += freq
    
    return (total_freq, known_freq, total_time, swap)
    
if __name__ == "__main__":
    curses.wrapper(main)