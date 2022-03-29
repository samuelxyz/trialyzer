# Entry point for the trialyzer application
# Contains main user interface and analysis features

import csv
import curses
import curses.textpad
import itertools
import json
import math
import multiprocessing
import operator
import os
import random
import statistics
import time
import typing
from typing import Callable, Iterable

import constraintmap
import gui_util
import layout
import remap
from remap import Remap
import typingtest
from fingermap import Finger
from constraintmap import Constraintmap
from nstroke import (Nstroke, Tristroke, all_bistroke_categories,
                     all_tristroke_categories, applicable_function,
                     bistroke_category, category_display_names, finger_names,
                     hand_names, tristroke_category)
from typingdata import TypingData


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
        try:
            active_constraintmap = constraintmap.get_constraintmap(
                settings["constraintmap"])
        except (KeyError, OSError):
            active_constraintmap = constraintmap.get_constraintmap(
                "traditional-default")
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
        active_constraintmap = constraintmap.get_constraintmap(
            "traditional-default")
        startup_messages.append(("Using default user settings", gui_util.red))

    typingdata_ = TypingData(active_speeds_file)

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
                trigram_freqs[tuple(item["Ngram"])] = item["Count"]
                included += item["Count"]
            total += item["Count"]

        return trigram_freqs, included/total
    
    def save_session_settings():
        with open("session_settings.json", "w") as settings_file:
            json.dump(
                {   "analysis_target": analysis_target.name,
                    "user_layout": user_layout.name,
                    "active_speeds_file": active_speeds_file,
                    "constraintmap": active_constraintmap.name,
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
            f"Generation constraintmap: {active_constraintmap.name}",
            f"Trigrams used: {precision_text} ({trigram_percent:.3%})"
        ]

    curses.curs_set(0)
    gui_util.init_colors()

    height, twidth = stdscr.getmaxyx()
    titlebar = stdscr.subwin(1,twidth,0,0)
    titlebar.bkgd(" ", curses.A_REVERSE)
    titlebar.addstr("Trialyzer" + " "*(twidth-10))
    titlebar.refresh()
    content_win = stdscr.subwin(1, 0)

    height, twidth = content_win.getmaxyx()
    startup_lines = len(header_text())
    message_win = content_win.derwin(
        height-startup_lines-2, int(twidth/3), startup_lines, 0)
    right_pane = content_win.derwin(
        height-startup_lines-2, int(twidth*2/3), startup_lines, 
        int(twidth/3))
    for win in (message_win, right_pane):
        win.scrollok(True)
        win.idlok(True)
    input_win = content_win.derwin(height-2, 2)
    input_box = curses.textpad.Textbox(input_win, True)
    
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

    def print_analysis_stats(stats: dict, header_line: str, 
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

        gui_util.insert_line_bottom(header_line, right_pane)
        right_pane.scroll(len(stats))
        ymax = right_pane.getmaxyx()[0]
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
            right_pane.addstr( # category name
                row, 0, ("{:" + pad_char + "<26}").format(category_name))
            right_pane.addstr( # freq
                row, 27, f"{stats[category][0]:>{s}6.2%}",
                pairs[0][category])
            right_pane.addstr( # known_freq
                row, 36, f"{stats[category][1]:>{s}6.2%}",
                pairs[1][category])
            right_pane.addstr( # speed
                row, 45, f"{stats[category][2]:>{s}6.1f}",
                pairs[2][category])
            right_pane.addstr( # contrib
                row, 53, f"{stats[category][3]:>{s}6.2f}",
                pairs[3][category])
            row += 1
        
        right_pane.refresh()

    def print_finger_stats(stats: dict):
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

        gui_util.insert_line_bottom(header_line, right_pane)
        right_pane.scroll(len(stats))
        ymax = right_pane.getmaxyx()[0]
        row = ymax - len(stats)

        # printing
        for category in categories:
            right_pane.addstr( # category name
                row, 0, f"{category:<{longest}}")
            right_pane.addstr( # lfreq
                row, longest+1, f"{stats[category][0]:>6.2%}",
                pairs[0][category])
            right_pane.addstr(row, longest+8, "|")
            right_pane.addstr( # tfreq
                row, longest+10, f"{stats[category][1]:>6.2%}",
                pairs[1][category])
            right_pane.addstr( # known
                row, longest+19, f"{stats[category][2]:>6.2%}",
                pairs[2][category])
            right_pane.addstr( # avg_ms
                row, longest+28, f"{stats[category][3]:>6.1f}",
                pairs[3][category])
            right_pane.addstr( # ms
                row, longest+36, f"{stats[category][4]:>6.2f}",
                pairs[4][category])
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

    def category_display_name(category: str):
        category_name = (category_display_names[category] 
            if category in category_display_names else category)
        if category.endswith(".") or not category:
            category_name += " (total)"
        return category_name
    
    def cmd_type():
        if not args: # autosuggest trigram
            # Choose the most frequent trigram from the least completed 
            # category of the analysis target layout
            with open("data/shai.json") as file:
                corpus = json.load(file)
            trigram_list = corpus["toptrigrams"]
            exact_tristrokes = typingdata_.exact_tristrokes_for_layout(
                analysis_target)
            catdata = typingdata_.tristroke_category_data(analysis_target)
            analysis_target.preprocessors["counts"].join()
            counts = analysis_target.counts
            completion = {}
            for cat in catdata:
                if cat.startswith(".") or cat.endswith(".") or cat == "":
                    continue
                n = catdata[cat][1]
                completion[cat] = n/counts[cat] if n > 0 else 0

            ruled_out = {analysis_target.to_ngram(tristroke)
                for tristroke in exact_tristrokes} # already have data
            trigram = None

            def find_from_best_cat():
                if not completion:
                    return None
                best_cat = min(completion, key = lambda cat: completion[cat])
                # trigram_list is sorted by descending frequency
                for entry in trigram_list:
                    ng = tuple(entry["Ngram"]) # tuple[str]
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
                return
            else:
                fingers = tuple(finger.name for finger in tristroke.fingers)
                message(f"Autosuggesting trigram {' '.join(trigram)}\n"
                    f"({analysis_target.name} "
                    f"{' '.join(analysis_target.to_ngram(tristroke))})\n"
                    "Be sure to use {} {} {}".format(*fingers),
                    gui_util.blue)
        elif len(args) == 3:
            tristroke = user_layout.to_nstroke(tuple(args))
        elif len(args) == 1 and len(args[0]) == 3:
            tristroke = user_layout.to_nstroke(tuple(args[0]))
        else:
            message("Malformed trigram", gui_util.red)
            return
        csvdata = typingdata_.csv_data
        if tristroke in csvdata:
            message(
                f"Note: this tristroke already has "
                f"{len(csvdata[tristroke][0])} data points",
                gui_util.blue)
        message("Starting typing test >>>", gui_util.green)
        typingtest.test(right_pane, tristroke, user_layout, csvdata)
        input_win.clear()
        typingdata_.save_csv()
        message("Typing data saved", gui_util.green)
        typingdata_.refresh()
    
    def cmd_clear():
        if len(args) == 3:
            trigram = tuple(args)
        elif len(args) == 1 and len(args[0]) == 3:
            trigram = tuple(args[0])
        else:
            message("Usage: c[lear] <trigram>", gui_util.red)
            return
        csvdata = typingdata_.csv_data
        tristroke = user_layout.to_nstroke(trigram)
        try:
            num_deleted = len(csvdata.pop(tristroke)[0])
        except KeyError:
            num_deleted = 0
        typingdata_.save_csv()
        typingdata_.refresh()
        message(f"Deleted {num_deleted} data points for {' '.join(trigram)}")

    def cmd_target():
        layout_name = " ".join(args)
        nonlocal analysis_target
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

    def cmd_layout():
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

    def cmd_list():
        try:
            page_num = int(args[0])
        except IndexError:
            page_num = 1
        except ValueError:
            message("Usage: list [page]", gui_util.red)
            return
        layout_file_list = scan_dir()
        if not layout_file_list:
            message("No layouts found in /layouts/", gui_util.red)
            return
        message(f"{len(layout_file_list)} layouts found", win=right_pane)
        first_row = 3
        num_rows = right_pane.getmaxyx()[0] - first_row
        names = [str(layout.get_layout(filename)) 
            for filename in layout_file_list]
        col_width = len(max(names, key=len))
        padding = 3
        num_cols =  (1 + 
            (right_pane.getmaxyx()[1] - col_width) // (col_width + padding))
        num_pages = math.ceil(len(names) / (num_rows * num_cols))
        if page_num > num_pages:
            page_num = num_pages
        elif page_num <= 0:
            page_num = 1
        message(f"Page {page_num} of {num_pages}"
            + " - Use list [page] to view others" * (num_pages > 1)
            + "\n---", 
            win=right_pane)
        first_index = (page_num - 1) * num_rows * num_cols
        last_index = min(len(names), first_index + num_rows * num_cols)
        right_pane.scroll(num_rows)
        for i in range(last_index - first_index):
            right_pane.addstr(
                first_row + i % num_rows, 
                (i // num_rows) * (col_width + padding),
                names[first_index + i])
        right_pane.refresh()

    def cmd_use():
        layout_name = " ".join(args)
        if layout_name: # set layout
            try:
                nonlocal user_layout
                user_layout = layout.get_layout(layout_name)
                message("Set " + layout_name + " as the user layout.",
                        gui_util.green)
                save_session_settings()
            except OSError:
                message(f"/layouts/{layout_name} was not found.", 
                        gui_util.red)

    def cmd_analyze(show_all: bool = False):
        if args:
            layout_name = " ".join(args)
            try:
                target_layout = layout.get_layout(layout_name)
            except OSError:
                message(f"/layouts/{layout_name} was not found.", 
                        gui_util.red)
                return
        else:
            target_layout = analysis_target
        message("Crunching the numbers >>>", gui_util.green)
        message_win.refresh()
        
        tri_stats = layout_tristroke_analysis(
            target_layout, typingdata_, trigram_freqs)
        bi_stats = layout_bistroke_analysis(
            target_layout, typingdata_)
        
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

        if show_all:
            tri_disp = tri_stats
            bi_disp = bi_stats
        else:
            tri_disp = {cat: vals for (cat, vals) in tri_stats.items()
                if vals[0] and not (
                    "scissor" in cat[2:] or "sfr" in cat or "sft" in cat)}
            bi_disp = {cat: vals for (cat, vals) in bi_stats.items()
                if vals[0] and ("scissor" not in cat or cat.startswith("."))}

        print_analysis_stats(tri_disp, tri_header_line)
        if not show_all:
            gui_util.insert_line_bottom("Use command \"fulla[nalyze]\" "
                "to see remaining categories", right_pane)
        print_analysis_stats(bi_disp, bi_header_line)

    def cmd_analyze_diff(show_all: bool = False):

        if not args:
            message("Usage: adiff [baseline_layout] <layout>", gui_util.red)
            return
        
        baseline_layout = None
        lay1, remain = extract_layout_front(args)
        if lay1:
            if remain:
                lay2, _ = extract_layout_front(remain, True)
                if lay2:
                    baseline_layout, target_layout = lay1, lay2
                else:
                    message(f"/layouts/{' '.join(remain)} was not found.",
                        gui_util.red)
                    return
            else:
                baseline_layout, target_layout = analysis_target, lay1
        else:
            message(f"/layouts/{' '.join(args)} was not found.",
                gui_util.red)
            return
        
        message("Crunching the numbers >>>", gui_util.green)
        message_win.refresh()
        
        analyze_diff_main(baseline_layout, target_layout, 
                          show_all, "fulladiff")

    def cmd_analyze_swap(show_all: bool = False):

        if not args:
            message("Usage: aswap [letter1 letter2] [...]", gui_util.red)
            return

        if len(args) % 2:
            message(f"{' '.join(args)} is an odd number of swaps "
                f"({len(args)}), should be even", gui_util.red)
            return
        
        baseline_layout = analysis_target
        swaps = args

        target_layout = layout.Layout(
            f"{baseline_layout.name}, swapped {' '.join(swaps)}", 
            False, repr(baseline_layout))
        try:
            while swaps:
                target_layout.remap((swaps.pop(0), swaps.pop(0)))
        except KeyError as ke:
            message(f"Key '{ke.args[0]}' does not exist "
                    f"in layout {baseline_layout.name}",
                    gui_util.red)
            return
        
        message("Crunching the numbers >>>", gui_util.green)
        message_win.refresh()

        if not show_all:
            message("\n" + target_layout.name + "\n"
                    + repr(target_layout), win=right_pane)
            right_pane.refresh()

        analyze_diff_main(baseline_layout, target_layout, 
                          show_all, "fullaswap")

    def analyze_diff_main(baseline_layout: layout.Layout, 
            target_layout: layout.Layout, show_all: bool, hint: str):
        
        base_tri_stats = layout_tristroke_analysis(
            baseline_layout, typingdata_, trigram_freqs)
        base_bi_stats = layout_bistroke_analysis(
            baseline_layout, typingdata_)
        base_tri_ms = base_tri_stats[""][2]
        base_tri_wpm = 24000/base_tri_ms
        base_bi_ms = base_bi_stats[""][2]
        base_bi_wpm = 12000/base_bi_ms

        tar_tri_stats = layout_tristroke_analysis(
            target_layout, typingdata_, trigram_freqs)
        tar_bi_stats = layout_bistroke_analysis(
            target_layout, typingdata_)
        tar_tri_ms = tar_tri_stats[""][2]
        tar_tri_wpm = 24000/tar_tri_ms
        tar_bi_ms = tar_bi_stats[""][2]
        tar_bi_wpm = 12000/tar_bi_ms

        def diff(target, baseline):
            return {key: 
                tuple(map(operator.sub, target[key], baseline[key]))
                for key in target}

        tri_stats = diff(tar_tri_stats, base_tri_stats)
        bi_stats = diff(tar_bi_stats, base_bi_stats)
        tri_ms = tar_tri_ms - base_tri_ms
        tri_wpm = tar_tri_wpm - base_tri_wpm
        bi_ms = tar_bi_ms - base_bi_ms
        bi_wpm = tar_bi_wpm - base_bi_wpm

        gui_util.insert_line_bottom(f"\nLayout {target_layout} "
            f"relative to {baseline_layout}", right_pane)
        gui_util.insert_line_bottom(
            f"Overall {tri_ms:+.2f} ms per trigram ({tri_wpm:+.2f} wpm)", right_pane)
        gui_util.insert_line_bottom(
            f"Overall {bi_ms:+.2f} ms per bigram ({bi_wpm:+.2f} wpm)", right_pane)
        
        tri_header_line = (
            "\nTristroke categories         freq    exact   avg_ms      ms")
        bi_header_line = (
            "\nBistroke categories          freq    exact   avg_ms      ms")

        if show_all:
            tri_disp = tri_stats
            bi_disp = bi_stats
        else:
            tri_disp = {cat: vals for (cat, vals) in tri_stats.items()
                if (tar_tri_stats[cat][0] or base_tri_stats[cat][0]) and not (
                    "scissor" in cat[2:] or "sfr" in cat or "sft" in cat)}
            bi_disp = {cat: vals for (cat, vals) in bi_stats.items()
                if (tar_bi_stats[cat][0] or base_bi_stats[cat][0]) and (
                    "scissor" not in cat or cat.startswith("."))}

        print_analysis_stats(tri_disp, tri_header_line, True)
        if not show_all:
            gui_util.insert_line_bottom(f"Use command \"{hint}\" "
                "to see remaining categories", right_pane)
        print_analysis_stats(bi_disp, bi_header_line, True)

    def cmd_dump():
        if args:
            if args[0] in ("a", "analysis"):
                cmd_dump_analysis()
                return
            elif args[0] in ("m", "medians"):
                cmd_dump_medians()
                return
        message("Usage: dump <a[nalysis]|m[edians]>", gui_util.red)
    
    def cmd_dump_analysis():
        layout_file_list = scan_dir()
        if not layout_file_list:
            message("No layouts found in /layouts/", gui_util.red)
            return
        message(f"Analyzing {len(layout_file_list)} layouts...", gui_util.green)
        layouts = [layout.get_layout(name) for name in layout_file_list]
        
        right_pane.scroll(2)
        rownum = right_pane.getmaxyx()[0] - 1
        tristroke_display_names = []
        for cat in sorted(all_tristroke_categories):
            try:
                tristroke_display_names.append(category_display_names[cat])
            except KeyError:
                tristroke_display_names.append(cat)
        bistroke_display_names = []
        for cat in sorted(all_bistroke_categories):
            try:
                bistroke_display_names.append(category_display_names[cat])
            except KeyError:
                bistroke_display_names.append(cat)
        header = ["name"]
        for cat in tristroke_display_names:
            for colname in ("freq", "exact", "avg_ms", "ms"):
                header.append(f"tristroke-{cat}-{colname}")
        for cat in bistroke_display_names:
            for colname in ("freq", "exact", "avg_ms", "ms"):
                header.append(f"bistroke-{cat}-{colname}")
        filename = find_free_filename("output/dump-analysis", ".csv")
        with open(filename, "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for i, lay in enumerate(layouts):
                tridata = layout_tristroke_analysis(lay, typingdata_, 
                    trigram_freqs)
                bidata = layout_bistroke_analysis(lay, typingdata_)
                right_pane.addstr(rownum, 0, 
                    f"Analyzed {i+1}/{len(layouts)} layouts")
                right_pane.refresh()
                row = [lay.name]
                for cat in sorted(all_tristroke_categories):
                    row.extend(tridata[cat])
                for cat in sorted(all_bistroke_categories):
                    row.extend(bidata[cat])
                row.extend(repr(lay).split("\n"))
                w.writerow(row)
        curses.beep()
        message(f"Done\nSaved as {filename}", gui_util.green, right_pane)

    def cmd_dump_medians():
        message("Crunching the numbers...", gui_util.green)
        tristroke_display_names = []
        for cat in sorted(all_tristroke_categories):
            try:
                tristroke_display_names.append(category_display_names[cat])
            except KeyError:
                tristroke_display_names.append(cat)
        header = ["trigram", "category", "ms_low", "ms_high", "ms_first", "ms_second", "ms_total"]
        exacts = typingdata_.exact_tristrokes_for_layout(analysis_target)
        
        filename = find_free_filename("output/dump-catmedians", ".csv")
        with open(filename, "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for tristroke in exacts:
                row = [" ".join(analysis_target.to_ngram(tristroke))]
                if not row:
                    continue
                row.append(tristroke_category(tristroke))
                row.extend(sorted(typingdata_.tri_medians[tristroke][:2]))
                row.extend(typingdata_.tri_medians[tristroke])
                w.writerow(row)
        message(f"Done\nSaved as {filename}", gui_util.green, right_pane)

    def cmd_fingers():
        if args:
            layout_name = " ".join(args)
            try:
                target_layout = layout.get_layout(layout_name)
            except OSError:
                message(f"/layouts/{layout_name} was not found.", 
                        gui_util.red)
                return
        else:
            target_layout = analysis_target
        message("Crunching the numbers >>>", gui_util.green)
        message_win.refresh()
        
        finger_stats = finger_analysis(
            target_layout, typingdata_, trigram_freqs)
        gui_util.insert_line_bottom("\nHand/finger breakdown for "
            f"{target_layout}", right_pane)
        print_finger_stats({k:v for k, v in finger_stats.items() if v[0]})

    def cmd_rank():
        output = False
        if "output" in args:
            args.remove("output")
            output = True
        layout_file_list = scan_dir()
        if not layout_file_list:
            message("No layouts found in /layouts/", gui_util.red)
            return
        message(f"Analyzing {len(layout_file_list)} layouts >>>", gui_util.green)
        layouts = [layout.get_layout(name) for name in layout_file_list]
        data = {}
        width = max(len(name) for name in layout_file_list)
        padding = 3
        col_width = width + 18 + 6
        header = "Layout" + " "*(width-3) + "avg_ms   wpm    exact"
        gui_util.insert_line_bottom(f"\n{header}", right_pane)
        ymax, xmax = right_pane.getmaxyx()
        first_row = ymax - len(layouts) - 2
        if first_row < 1:
            first_row = 1
        right_pane.scroll(min(ymax-1, len(layouts) + 2))
        num_cols = (xmax + padding)//(col_width + padding)

        col_settings = (
            {"transform": math.sqrt, "worst": gui_util.MAD_z(5), 
                "best": gui_util.MAD_z(-5)}, # avg_ms
            {"transform": math.sqrt, "best": gui_util.MAD_z(5), 
                "worst": gui_util.MAD_z(-5)}, # exact
        )

        num_rows = ymax - first_row

        def print_row():
            nonlocal row
            nonlocal col
            right_pane.move(row, col)
            right_pane.clrtoeol()
            right_pane.addstr(
                row, col, f"{lay:{width}s}")
            right_pane.addstr( # avg_ms
                row, col+width+3, f"{data[lay][0]:6.2f}",
                pairs[0][lay])
            right_pane.addstr( # wpm
                row, col+width+12, f"{int(24000/data[lay][0]):3}",
                pairs[0][lay])
            right_pane.addstr( # exact
                row, col+width+18, f"{data[lay][1]:6.2%}",
                pairs[1][lay])
            row += 1

        # analyze all
        for lay in layouts:
            data[lay.name] = layout_speed(lay, typingdata_, trigram_freqs)
            row = first_row
            sorted_ = list(sorted(data, key=lambda d: data[d][0]))
            displayed = {sorted_[i]: data[sorted_[i]] 
                for i in range(len(sorted_)) if i < num_rows*num_cols}
            pairs = gui_util.apply_scales(displayed, col_settings)
            col = 0
            # print ranking as of each step
            for lay in displayed:
                try:
                    print_row()
                except curses.error: # maxed out first row
                    row = first_row
                    col += col_width + padding
                    try:
                        right_pane.addstr(row-1, col, header)
                        print_row()
                    except curses.error:
                        break
            right_pane.refresh()
        curses.beep()
        message(f"Ranking complete", gui_util.green)
        if output:
            header = ["name", "avg_ms", "exact"]
            filename = find_free_filename("output/ranking", ".csv")
            with open(filename, "w", newline="") as csvfile:
                w = csv.writer(csvfile)
                w.writerow(header)
                for lay in layouts:
                    row = [lay.name]
                    row.extend(data[lay.name])
                    row.extend(repr(lay).split("\n"))
                    w.writerow(row)
            message(f"Saved ranking as {filename}", gui_util.green)

    def cmd_rt():
        reverse_opts = {"min": False, "max": True}
        analysis_opts = {"freq": 0, "exact": 1, "avg_ms": 2, "ms": 3}
        try:
            reverse_ = reverse_opts[args[0]]
            sorting_col = analysis_opts[args[1]]
        except (KeyError, IndexError):
            message("Usage: rt <min|max> <freq|exact|avg_ms|ms> [category]",
                gui_util.red)
            return
        try:
            category = parse_category(args[2])
            if category is None:
                return
        except IndexError:
            category = ""
        category_name = category_display_name(category)

        layout_file_list = scan_dir()
        if not layout_file_list:
            message("No layouts found in /layouts/", gui_util.red)
            return
        message(f"Analyzing {len(layout_file_list)} layouts >>>",
            gui_util.green)
        width = max(len(name) for name in layout_file_list)
        padding = 3
        header = (f"Ranking by tristroke category: {category_name}, "
            f"{args[0]} {args[1]} first", 
            "Layout" + " "*(width-1) + "freq    exact   avg_ms      ms")
        headerjoin = '\n'.join(header) # not allowed inside f-string
        gui_util.insert_line_bottom(f"\n{headerjoin}", right_pane)
        col_width = width + 29 + 6
        ymax, xmax = right_pane.getmaxyx()
        first_row = ymax - len(layout_file_list) - 3
        if first_row < 2:
            first_row = 2
        right_pane.scroll(min(ymax-2, len(layout_file_list) + 1))
        right_pane.refresh()
        num_cols = (xmax + padding)//(col_width + padding)
        layouts = [layout.get_layout(name) for name in layout_file_list]
        num_rows = ymax - first_row

        data = {}

        col_settings = [ # for colors
            {"transform": math.sqrt, "best": gui_util.MAD_z(5), 
                "worst": gui_util.MAD_z(-5)}, # freq
            {"transform": math.sqrt, "best": gui_util.MAD_z(5), 
                "worst": gui_util.MAD_z(-5)}, # exact
            {"worst": gui_util.MAD_z(5), 
                "best": gui_util.MAD_z(-5)}, # avg_ms
            {"transform": math.sqrt, "worst": gui_util.MAD_z(5), 
                "best": gui_util.MAD_z(-5)}, # ms
        ]
        col_settings_inverted = col_settings.copy()
        col_settings_inverted[0] = col_settings_inverted[3]

        def print_row():
            nonlocal row
            nonlocal col
            right_pane.move(row, col)
            right_pane.clrtoeol()
            right_pane.addstr(
                row, col, f"{rowname:{width}s}   ")
            right_pane.addstr( # freq
                row, col+width+3, f"{rows[rowname][0]:>6.2%}",
                pairs[0][rowname])
            right_pane.addstr( # exact
                row, col+width+12, f"{rows[rowname][1]:>6.2%}",
                pairs[1][rowname])
            right_pane.addstr( # avg_ms
                row, col+width+21, f"{rows[rowname][2]:>6.1f}",
                pairs[2][rowname])
            right_pane.addstr( # ms
                row, col+width+29, f"{rows[rowname][3]:>6.2f}",
                pairs[3][rowname])
            row += 1
        
        for lay in layouts:
            data[lay.name] = layout_tristroke_analysis(
                lay, typingdata_, trigram_freqs)
            row = first_row
            col = 0
            
            # color freq by whether the category is faster than total
            try:
                this_avg = statistics.fmean(
                    data[layname][category][2] for layname in data)
                total_avg = statistics.fmean(
                    data[layname][""][2] for layname in data)
                invert = this_avg > total_avg
            except statistics.StatisticsError:
                invert = False
            names = list(sorted(
                data, key=lambda name: data[name][category][sorting_col], 
                reverse=reverse_))
            rows = {name: data[name][category] 
                for i, name in enumerate(names) if i < num_rows*num_cols}
            if invert:
                pairs = gui_util.apply_scales(
                    rows, col_settings_inverted)    
            else:
                pairs = gui_util.apply_scales(rows, col_settings)

            # printing
            for rowname in rows:
                try:
                    print_row()
                except curses.error:
                    row = first_row
                    col += col_width + padding
                    try:
                        # right_pane.addstr(row-2, col, header[0])
                        right_pane.addstr(row-1, col, header[1])
                        print_row()
                    except curses.error:
                        break
            right_pane.refresh()
        curses.beep()
        message(f"Ranking complete", gui_util.green)

    def cmd_bistroke():
        if not args:
            message("Crunching the numbers >>>", gui_util.green)
            message_win.refresh()
            right_pane.clear()
            print_stroke_categories(
                typingdata_.bistroke_category_data(analysis_target))
        else:
            message("Individual bistroke stats are"
                " not yet implemented", gui_util.red)

    def cmd_tristroke():
        if not args:
            message("Crunching the numbers >>>", gui_util.green)
            right_pane.clear()
            data = typingdata_.tristroke_category_data(analysis_target)
            header_line = (
                "Category                       ms    n     possible")
            gui_util.insert_line_bottom(header_line, right_pane)
            analysis_target.preprocessors["counts"].join()
            print_stroke_categories(data, analysis_target.counts)
        else:
            message("Individual tristroke stats are"
                " not yet implemented", gui_util.red)

    def cmd_speeds_file():
        nonlocal active_speeds_file
        if not args:
            active_speeds_file = "default"
        else:
            active_speeds_file = " ".join(args)
        nonlocal typingdata_
        typingdata_ = TypingData(active_speeds_file)
        message(f"Set active speeds file to /data/{active_speeds_file}.csv",
                gui_util.green)
        if not os.path.exists(f"data/{active_speeds_file}.csv"):
            message("The new file will be written upon save", gui_util.blue)
        save_session_settings()

    def cmd_improve():
        nonlocal analysis_target
        pins = []
        if "pin" in args:
            while True:
                token = args.pop()
                if token == "pin":
                    break
                else:
                    pins.append(token)
        if args:
            layout_, _ = extract_layout_front(args)
            if layout_ is not None:
                target_layout = layout_
            else:
                message(f"/layouts/{' '.join(args)} was not found", 
                    gui_util.red)
                return
        else:
            target_layout = analysis_target
        message("Using steepest ascent... >>>", gui_util.green)
        
        initial_score = layout_speed(
            target_layout, typingdata_, trigram_freqs)[0]
        message(f"\nInitial layout: avg_ms = {initial_score:.4f}\n"
            + repr(target_layout), win=right_pane)
        
        num_swaps = 0
        optimized = target_layout
        for optimized, score, remap_ in steepest_ascent(
            target_layout, typingdata_, trigram_freqs, 
            active_constraintmap, pins
        ):
            num_swaps += 1
            repr_ = repr(optimized)
            message(f"Edit #{num_swaps}: avg_ms = {score:.4f} ({remap_})"
                f"\n{repr_}", win=right_pane)
        curses.beep()
        message(f"Local optimum reached", gui_util.green, right_pane)
        
        if optimized is not target_layout:
            with open(f"layouts/{optimized.name}", "w") as file:
                    file.write(repr_)
            message(
                f"Saved new layout as {optimized.name}\n"
                "Set as analysis target",
                gui_util.green, right_pane)
            # reload from file in case
            layout.Layout.loaded[optimized.name] = layout.Layout(
                optimized.name)
            analysis_target = layout.get_layout(optimized.name)
            save_session_settings()

    def cmd_si():
        nonlocal analysis_target
        num_iterations = 10 # reasonable default
        for item in args:
            try:
                num_iterations = int(item)
                args.remove(item)
                break
            except ValueError:
                continue        
        pins = []
        if "pin" in args:
            while True:
                token = args.pop()
                if token == "pin":
                    break
                else:
                    pins.append(token)
        if args:
            layout_, _ = extract_layout_front(args)
            if layout_ is not None:
                target_layout = layout_
            else:
                message(f"/layouts/{' '.join(args)} was not found", 
                    gui_util.red)
                return
        else:
            target_layout = analysis_target
        pin_positions = {key: target_layout.positions[key] for key in pins}
        try: # load existing best if present
            working_lay = layout.Layout(target_layout.name + "-best", False)
        except OSError:
            working_lay = layout.Layout(target_layout.name, False)
        for key in pin_positions:
            if pin_positions[key] != working_lay.positions[key]:
                working_lay = layout.Layout(target_layout.name, False)
                break

        # ideally this wouldn't be necessary, but pins exceeding the pinky cap
        # would cause trouble. Maybe improve this in the future
        # finger_freqs = working_lay.frequency_by_finger()
        # initial_pinky_freq = max(
        #     finger_freqs[Finger.RP], finger_freqs[Finger.LP])
        # if pinky_cap < initial_pinky_freq:
        #     pinky_cap = initial_pinky_freq

        message("Shuffling & ascending... >>>", gui_util.green)
        
        best_score = layout_speed(
                working_lay, typingdata_, trigram_freqs)[0]
        message(f"Initial best: avg_ms = {best_score:.4f}\n"
                + repr(working_lay), win=right_pane)

        with open("data/shai.json") as file:
            corp_data = json.load(file)
        lfreqs = corp_data["letters"]
        total_lfreq = sum(lfreqs[key] for key in working_lay.positions
            if key in lfreqs)
        for key in lfreqs:
            lfreqs[key] /= total_lfreq

        def shuffle_source():
            return active_constraintmap.random_legal_swap(
                working_lay, lfreqs, pins)

        for iteration in range(num_iterations):
            working_lay.constrained_shuffle(shuffle_source)
            num_shuffles = 0
            while (not active_constraintmap.is_layout_legal(working_lay, lfreqs)):
                working_lay.constrained_shuffle(shuffle_source)
                num_shuffles += 1
                if num_shuffles >= 100000:
                    message("Unable to satisfy constraintmap after shuffling"
                        f" {num_shuffles} times. Constraintmap/pins might be"
                        " too strict?", gui_util.red, right_pane)
                    return
            initial_score = layout_speed(
                working_lay, typingdata_, trigram_freqs)[0]
            message(f"\nShuffle/Attempt {iteration}\n"
                f"Initial shuffle: avg_ms = {initial_score:.4f}\n"
                + repr(working_lay), win=right_pane)
            
            num_swaps = 0
            optimized = working_lay
            for optimized, score, remap_ in steepest_ascent(
                working_lay, typingdata_, trigram_freqs, active_constraintmap,
                pins, "-best"
            ):
                num_swaps += 1
                repr_ = repr(optimized)
                message(f"Edit #{iteration}.{num_swaps}: avg_ms = {score:.4f}"
                    f" ({remap_})\n{repr_}", win=right_pane)
            message(f"Local optimum reached", gui_util.green, right_pane)
            
            if optimized is not working_lay and score < best_score:
                message(
                    f"New best score of {score:.4f}\n"
                    f"Saved as layouts/{optimized.name}", 
                    gui_util.green, right_pane)
                best_score = score
                with open(f"layouts/{optimized.name}", "w") as file:
                        file.write(repr_)
        message("\nSet best as analysis target",
            gui_util.green, right_pane)
        # reload from file in case
        curses.beep()
        try:
            layout.Layout.loaded[optimized.name] = layout.Layout(
                optimized.name)
            analysis_target = layout.get_layout(optimized.name)
            save_session_settings()
        except OSError: # no improvement found
            return

    def cmd_anneal():
        nonlocal analysis_target
        num_iterations = 10000 # reasonable default
        for item in args:
            try:
                num_iterations = int(item)
                args.remove(item)
                break
            except ValueError:
                continue
        pins = []
        if "pin" in args:
            while True:
                token = args.pop()
                if token == "pin":
                    break
                else:
                    pins.append(token)
        if args:
            layout_, _ = extract_layout_front(args)
            if layout_ is not None:
                target_layout = layout_
            else:
                message(f"/layouts/{' '.join(args)} was not found", 
                    gui_util.red)
                return
        else:
            target_layout = analysis_target

        message("Annealing... >>>", gui_util.green)

        initial_score = layout_speed(
            target_layout, typingdata_, trigram_freqs)[0]
        message(
            f"Initial score: avg_ms = {initial_score:.4f}\n"
            + repr(target_layout), win=right_pane)
        
        last_time = -1
        optimized = target_layout
        for optimized, i, temperature, delta, score, remap_ in anneal(
            target_layout, typingdata_, trigram_freqs, active_constraintmap,
            pins, "-annealed", num_iterations
        ):
            current_time = time.perf_counter()
            if current_time - last_time < 0.5:
                continue
            last_time = current_time
            repr_ = repr(optimized)
            message(
                f"{i/num_iterations:.2%} progress, "
                f"temperature = {temperature:.4f}, delta = {delta:.4f}\n"
                f"avg_ms = {score:.4f}, last edit: {remap_}\n"
                f"{repr_}", win=right_pane)
        i = 1
        path_ = find_free_filename(f"layouts/{optimized.name}")
        with open(path_, "w") as file:
                file.write(repr(optimized))
        optimized.name = path_[8:]
        curses.beep()
        message(
            f"Annealing complete\nSaved as {path_}"
            "\nSet as analysis target", 
            gui_util.green, right_pane)
        layout.Layout.loaded[optimized.name] = layout.Layout(
            optimized.name)
        analysis_target = layout.get_layout(optimized.name)
        save_session_settings()

    def cmd_precision():
        nonlocal trigram_freqs
        nonlocal trigram_precision
        nonlocal trigram_percent
        try:
            trigram_precision = int(args[0])
        except IndexError:
            message("Usage: precision <n>\nOr use \"precision full\"",
                gui_util.red)
            return
        except ValueError:
            if args[0] == "full":
                trigram_precision = 0
            else:
                message("Precision must be an integer", gui_util.red)
                return
        trigram_freqs, trigram_percent = load_trigrams(trigram_precision)
        save_session_settings()
        message(f"Set trigram precision to {args[0]} ({trigram_percent:.3%})", 
            gui_util.green)

    def cmd_constraintmap():
        nonlocal active_constraintmap
        try: 
            active_constraintmap = constraintmap.get_constraintmap(
                " ".join(args))
            save_session_settings()
            message(f"Set constraintmap to {active_constraintmap.name}",
                gui_util.green)
        except OSError:
            message(f"/constraintmaps/{' '.join(args)} was not found.",
                gui_util.red)

    def cmd_help():
        help_text = [
            "",
            "",
            "Command <required thing> [optional thing] option1|option2",
            "-----Repeating a command-----",
            "Precede with a number to repeat the command n times.",
            "For example, '10 anneal QWERTY'",
            "------General commands------",
            "h[elp]: Show this list",
            "reload [layout name]: Reload layout(s) from files",
            "precision <n|full>: "
                "Set analysis to use the top n trigrams, or all",
            "l[ayout] [layout name]: View layout",
            "list [page]: List all layouts",
            "q[uit]",
            "----Typing data commands----",
            "u[se] <layout name>: Set layout used in typing test",
            "t[ype] [trigram]: Run typing test",
            "c[lear] <trigram>: Erase data for trigram",
            "df [filename]: Set typing data file, or use default",
            "-----Analysis commands-----",
            "target <layout name>: Set analysis target (for other commands)",
            "a[nalyze] [layout name]: Detailed layout analysis",
            "fulla[nalyze] [layout name]: Like analyze but even more detailed",
            "a[nalyze]diff [baseline_layout] <layout>: "
                "Like analyze but compares two layouts",
            "a[nalyze]swap [letter1 letter2] [...]: Analyze a swap",
            "f[ingers] [layout name]: Hand/finger usage breakdown",
            "r[ank]: Rank all layouts by wpm",
            "rt <min|max> <freq|exact|avg_ms|ms> [category]: "
                "Rank by tristroke statistic",
            "draw [<freq|exact|avg_ms|ms> [category]]: Draw or heatmap",
            "dump <a[nalysis]|m[edians]>: Write some data to a csv",
            "bs [bistroke]: Show specified/all bistroke stats",
            "ts [tristroke]: Show specified/all tristroke stats",
            "tsc [category]: Show tristroke category/total stats",
            "tgc [category] [with <fingers>] [without <fingers>]: "
                "Show speeds and trigrams of interest in recorded data",
            "tgcdiff [baseline_layout] <layout> <args for tgc>: "
                "Like tgc but shows how trigrams vary between layouts",
            "----Editing/Optimization----",
            "cm|constraintmap [constraintmap name]: Set constraintmap",
            "i[mprove]|ascend [layout name] [pin <keys>]: "
                "Optimize using steepest ascent swaps",
            "si [layout name] [n] [pin <keys>]: "
                "Shuffle and run steepest ascent n times, saving the best",
            "anneal [layout name] [n] [pin <keys>]: "
                "Optimize with simulated annealing"
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

    def cmd_tsc():
        if not args:
            category = ""
        else:
            category = parse_category(args[0])
            if category is None:
                return
        
        message("Crunching the numbers >>>", gui_util.green)
        data = data_for_tristroke_category(
            category, analysis_target, typingdata_)
        (speed, num_samples, with_fingers, without_fingers) = data
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

    def cmd_tgc():
        with_fingers = set()
        without_fingers = set()
        try:
            for i in reversed(range(len(args))):
                if args[i] == "with":
                    for _ in range(len(args)-i-1):
                        with_fingers.add(Finger[args.pop()])
                    args.pop() # remove "with"
                elif args[i] == "without":
                    for _ in range(len(args)-i-1):
                        without_fingers.add(Finger[args.pop()])
                    args.pop() # remove "without"
        except KeyError:
            message("Usage:\n"
                "tgc [category] [with <fingers>] [without <fingers>]",
                gui_util.red)
            return
        if not with_fingers:
            with_fingers = set(Finger)
        with_fingers -= without_fingers
        if not args:
            category = ""
        else:
            category = parse_category(args[0])
            if category is None:
                if extract_layout_front(args)[0]:
                    message("Did you mean to use tgcdiff?", gui_util.red)
                return
                    
        message("Crunching the numbers >>>", gui_util.green)

        stats = trigrams_with_specifications(
            typingdata_, trigram_freqs, analysis_target, category, 
            with_fingers, without_fingers
        )
        overall = stats.pop("")
        display_name = (category_display_names[category] 
            if category in category_display_names else category)

        right_pane.scroll(1)
        header = (
            str(analysis_target),
            f"Tristroke category: {display_name}",
            f"With: {' '.join(f.name for f in with_fingers)}",
            f"Without: {' '.join(f.name for f in without_fingers)}",
            "Trigrams in gray have their speeds guessed (inexact)",
            "Overall:  freq   avg_ms       ms   exact",
            "      {:>8.3%}   {:>6.1f}  {:>7.3f}   {:6.2%}".format(*overall),
        )
        message("\n".join(header), win=right_pane)
        gray = curses.color_pair(gui_util.gray)
        right_pane.addstr(right_pane.getmaxyx()[0]-3, 12, "gray", gray)

        num_rows = right_pane.getmaxyx()[0] - len(header)
        rows_each = int(num_rows/3) - 3
        first_row = right_pane.getmaxyx()[0] - rows_each
        best_trigrams = sorted(stats, key=lambda t: stats[t][1])
        worst_trigrams = sorted(
            stats, key=lambda t: stats[t][2], reverse=True)
        frequent_trigrams = sorted(
            stats, key=lambda t: stats[t][0], reverse=True)
        if len(best_trigrams) > rows_each:
            best_trigrams = best_trigrams[:rows_each]
            worst_trigrams = worst_trigrams[:rows_each]
            frequent_trigrams = frequent_trigrams[:rows_each]
        visible_trigrams = best_trigrams + worst_trigrams + frequent_trigrams
        twidth = max(len(" ".join(t)) for t in visible_trigrams)        
        stats = {t: s for t, s in stats.items() if t in visible_trigrams}

        col_settings = [ # for colors
            {"transform": math.sqrt}, # freq
            {"worst": max, "best": min}, # avg_ms
            {"transform": math.sqrt, "worst": max, "best": min}, # ms
        ]
        pairs = gui_util.apply_scales(stats, col_settings)

        for list_, listname in zip(
                (best_trigrams, worst_trigrams, frequent_trigrams),
                ("Fastest:", "Highest impact:", "Most frequent:")):
            message(f"\n{listname}\n" + " "*twidth + 
                "     freq   avg_ms       ms   category", win=right_pane)
            right_pane.scroll(rows_each)
            row = first_row
            for tg in list_:
                right_pane.move(row, 0)
                right_pane.clrtoeol()
                right_pane.addstr(
                    row, 0, f"{' '.join(tg):{twidth}s}   ",
                    0 if stats[tg][3] else gray)
                right_pane.addstr( # freq
                    row, twidth+2, f"{stats[tg][0]:>7.3%}",
                    pairs[0][tg])
                right_pane.addstr( # avg_ms
                    row, twidth+12, f"{stats[tg][1]:>6.1f}",
                    pairs[1][tg])
                right_pane.addstr( # ms
                    row, twidth+21, f"{stats[tg][2]:>6.3f}",
                    pairs[2][tg])
                right_pane.addstr( # category
                    row, twidth+30, 
                    tristroke_category(analysis_target.to_nstroke(tg)))
                row += 1
        right_pane.refresh()

    def cmd_tgc_diff():
        if not args:
            message("Usage: tgcdiff [baseline_layout] <layout> [category] "
                "[with <fingers>] [without <fingers>]", gui_util.red)
            return
        
        lay1, remain = extract_layout_front(args)
        if lay1:
            if remain:
                lay2, remain = extract_layout_front(remain)
                if lay2:
                    baseline_layout, target_layout = lay1, lay2
                else:
                    message(f"/layouts/{' '.join(remain)} was not found.",
                        gui_util.red)
                    return
            else:
                baseline_layout, target_layout = analysis_target, lay1
        else:
            message(f"/layouts/{' '.join(args)} was not found.",
                gui_util.red)
            return

        with_fingers = set()
        without_fingers = set()
        try:
            for i in reversed(range(len(remain))):
                if remain[i] == "with":
                    for _ in range(len(remain)-i-1):
                        with_fingers.add(Finger[remain.pop()])
                    remain.pop() # remove "with"
                elif remain[i] == "without":
                    for _ in range(len(remain)-i-1):
                        without_fingers.add(Finger[remain.pop()])
                    remain.pop() # remove "without"
        except KeyError:
            message("Usage: tgcdiff [baseline_layout] <layout> [category] "
                "[with <fingers>] [without <fingers>]", gui_util.red)
            return
        if not with_fingers:
            with_fingers = set(Finger)
        with_fingers -= without_fingers
        if not remain:
            category = ""
        else:
            category = parse_category(remain[0])
            if category is None:
                return
        
        message("Crunching the numbers >>>", gui_util.green)
        message_win.refresh()
        
        tgc_diff_main(baseline_layout, target_layout, category, 
            with_fingers, without_fingers)

    def tgc_diff_main(
            baseline_layout: layout.Layout, target_layout: layout.Layout, 
            category: str, 
            with_fingers: set[Finger], without_fingers: set[Finger]):
        base_stats = trigrams_with_specifications(
            typingdata_, trigram_freqs, baseline_layout, category, 
            with_fingers, without_fingers
        )
        base_overall = base_stats.pop("")
        tar_stats = trigrams_in_list(
            base_stats, typingdata_, target_layout, trigram_freqs)
        tar_overall = tar_stats.pop("")

        # maybe something fancy should be done with any trigrams that
        # don't exist in both layouts, but for now we just drop them
        stats = dict()
        for trigram, base in base_stats.items():
            try:
                tar = tar_stats[trigram]
            except KeyError:
                continue
            if tar[1] == base[1]:
                continue
            stats[trigram] = (
                base[0], # freq
                tar[1] - base[1], # avg_ms
                tar[2] - base[2], # ms
                tar[3] and base[3], # exact
                tristroke_category(baseline_layout.to_nstroke(trigram)),
                tristroke_category(target_layout.to_nstroke(trigram)),
            )
        overall = tuple(map(operator.sub, tar_overall, base_overall))

        display_name = (category_display_names[category] 
            if category in category_display_names else category)

        header = (
            f"{str(target_layout)} relative to {str(baseline_layout)}",
            f"Trigram category: {display_name}",
            f"With: {' '.join(f.name for f in with_fingers)}",
            f"Without: {' '.join(f.name for f in without_fingers)}",
            "Trigrams in gray have their speeds guessed (inexact)",
            "Overall:  freq   avg_ms       ms   exact",
            "      {:>+8.3%}   {:>+6.1f}  {:>+7.3f}   {:+6.2%}".format(
                *overall),
        )
        message("\n".join(header), win=right_pane)
        gray = curses.color_pair(gui_util.gray)
        right_pane.addstr(right_pane.getmaxyx()[0]-3, 12, "gray", gray)

        num_rows = right_pane.getmaxyx()[0] - len(header)
        rows_each = int(num_rows/3) - 3
        first_row = right_pane.getmaxyx()[0] - rows_each
        best_trigrams = sorted(stats, key=lambda t: stats[t][2])
        worst_trigrams = list(reversed(best_trigrams))
        frequent_trigrams = sorted(
            stats, key=lambda t: stats[t][0], reverse=True)
        if len(best_trigrams) > rows_each:
            best_trigrams = best_trigrams[:rows_each]
            worst_trigrams = worst_trigrams[:rows_each]
            frequent_trigrams = frequent_trigrams[:rows_each]
        visible_trigrams = set(
            best_trigrams + worst_trigrams + frequent_trigrams)
        twidth = max((len(" ".join(t)) for t in visible_trigrams), default=5)
        cat_width = max((len(stats[t][4]) for t in visible_trigrams), 
            default=12)
        stats = {t: s for t, s in stats.items() if t in visible_trigrams}

        col_settings = (
            {"transform": math.sqrt}, # freq
            {"worst": gui_util.extreme, "best": gui_util.neg_extreme}, # avg_ms
            {"transform": gui_util.odd_sqrt, "worst": gui_util.extreme, 
                "best": gui_util.neg_extreme}, # ms
        )
        pairs = gui_util.apply_scales(stats, col_settings)

        for list_, listname in zip(
                (best_trigrams, worst_trigrams, frequent_trigrams),
                ("Most improved:", "Most worsened:", "Most frequent:")):
            message(f"\n{listname}\n{' '*twidth}" 
                f"     freq   avg_ms       ms   {'old category':{cat_width}}"
                "   new category",
                win=right_pane)
            right_pane.scroll(rows_each)
            row = first_row
            for tg in list_:
                right_pane.move(row, 0)
                right_pane.clrtoeol()
                right_pane.addstr(
                    row, 0, f"{' '.join(tg):{twidth}s}   ",
                    0 if stats[tg][3] else gray)
                right_pane.addstr( # freq
                    row, twidth+2, f"{stats[tg][0]:>7.3%}",
                    pairs[0][tg])
                right_pane.addstr( # avg_ms
                    row, twidth+12, f"{stats[tg][1]:>+6.1f}",
                    pairs[1][tg])
                right_pane.addstr( # ms
                    row, twidth+21, f"{stats[tg][2]:>+6.3f}",
                    pairs[2][tg])
                right_pane.addstr( # category1
                    row, twidth+30, stats[tg][4])
                right_pane.addstr( # category2
                    row, twidth+33+cat_width, stats[tg][5])
                row += 1
        right_pane.refresh()

    def cmd_reload():
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
                return
        else:
            to_delete = []
            for layout_name in layout.Layout.loaded:
                try:
                    layout.Layout.loaded[layout_name] = layout.Layout(
                        layout_name)
                except OSError:
                    to_delete.append(layout_name)
            for layout_name in to_delete:
                del layout.Layout.loaded[layout_name]
            message("Reloaded all layouts", gui_util.green)
        nonlocal user_layout
        try:
            user_layout = layout.get_layout(user_layout.name)
        except OSError:
            user_layout = layout.get_layout("qwerty")
        nonlocal analysis_target
        try:
            analysis_target = layout.get_layout(analysis_target.name)
        except OSError:
            analysis_target = layout.get_layout("qwerty")

    def cmd_draw():
        coords = analysis_target.coords # dict[key, coord]
        if args:
            analysis_opts = {"freq": 0, "exact": 1, "avg_ms": 2, "ms": 3}
            color_settings_opts = [ # for colors
                {"transform": math.sqrt}, # freq
                {"transform": math.sqrt}, # exact
                {"worst": max, "best": min}, # avg_ms
                {"transform": math.sqrt, "worst": max, "best": min}, # ms
            ]
            try:
                sorting_col = analysis_opts[args[0]]
                color_settings = color_settings_opts[sorting_col]
            except (KeyError, IndexError):
                message("Usage: draw [<freq|exact|avg_ms|ms> [category]]",
                    gui_util.red)
                return
            try:
                category = parse_category(args[1])
                if category is None:
                    return
            except IndexError:
                category = ""
            category_name = category_display_name(category)

            stats = key_analysis(
                analysis_target, typingdata_, trigram_freqs)
            color_stat = {
                key: (stats[key][category][sorting_col],) for key in stats}
            pairs = gui_util.apply_scales(color_stat, (color_settings,))[0]
            message(f"\n{analysis_target.name} heatmap by "
                f"tristroke {category_name} {args[0]}\n", 
                win=right_pane)
        else:
            pairs = {key: curses.color_pair(0) for key in coords}
            message(f"\n{analysis_target.name}\n", win=right_pane)

        x_scale = 4
        y_scale = -2
        max_y = max(coords.values(), key=lambda c: c.y).y
        min_y = min(coords.values(), key=lambda c: c.y).y
        min_x = min(coords.values(), key=lambda c: c.x).x
        num_lines = abs(int(y_scale*(max_y - min_y)))+1
        right_pane.scroll(num_lines)
        first_row = right_pane.getmaxyx()[0] - num_lines
        first_col = 0
        origin_row = first_row - max_y*y_scale
        origin_col = first_col - min_x*x_scale
        for key in coords:
            try:
                right_pane.addstr(
                    int(origin_row + y_scale*coords[key].y), 
                    int(origin_col + x_scale*coords[key].x),
                    key, pairs[key]
                )
            except curses.error:
                pass
        right_pane.refresh()

    def cmd_debug():
        gui_util.debug_win(message_win, "message_win")
        gui_util.debug_win(right_pane, "right_pane")

    def cmd_colors():
        message("COLORS: {}".format(curses.COLORS))
        message("COLOR_PAIRS: {}".format(curses.COLOR_PAIRS))
        ymax = right_pane.getmaxyx()[0]
        for i in range(curses.COLOR_PAIRS):
            right_pane.addstr(
                i % ymax, 9*int(i/ymax), 
                "Color {}".format(i), curses.color_pair(i))
        right_pane.refresh()

    def cmd_gradient():
        for i, color in enumerate(gui_util.gradient_colors):
            message("Gradient level {}".format(i), color)

    def cmd_unrecognized():
        message("Unrecognized command", gui_util.red)

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
        try:
            num_repetitions = int(command)
            command = args.pop(0).lower()
        except ValueError:
            num_repetitions = 1
        original_args = args.copy()
        
        for _ in range(num_repetitions):
            args = original_args.copy()
            if command in ("q", "quit"):
                return
            elif command in ("t", "type"):
                cmd_type()
            elif command in ("c", "clear"):
                cmd_clear()
            elif command == "target":
                cmd_target()
            elif command in ("l", "layout"):
                cmd_layout()
            elif command in ("list",):
                cmd_list()
            elif command in ("u", "use"):
                cmd_use()
            elif command in ("a", "analyze"):
                cmd_layout()
                cmd_analyze()
                cmd_fingers()
            elif command in ("fulla", "fullanalyze"):
                cmd_analyze(True)
            elif command in ("diffa", "adiff", 'analyzediff'):
                cmd_analyze_diff()
            elif command in ("fulladiff",):
                cmd_analyze_diff(True)
            elif command in ("aswap", "analyzeswap"):
                cmd_analyze_swap()
            elif command in ("fullaswap",):
                cmd_analyze_swap(True)
            elif command == "dump":
                cmd_dump()
            elif command in ("f", "fingers"):
                cmd_fingers()
            elif command in ("r", "rank"):
                cmd_rank()
            elif command == "rt":
                cmd_rt()
            elif command in ("bs", "bistroke"):
                cmd_bistroke()
            elif command in ("ts", "tristroke"):
                cmd_tristroke()
            elif command == "df":
                cmd_speeds_file()
            elif command in ("i", "improve", "ascend"):
                cmd_improve()
            elif command in ("si",):
                cmd_si()
            elif command in ("anneal",):
                cmd_anneal()
            elif command == "precision":
                cmd_precision()
            elif command in ("cm", "constraintmap"):
                cmd_constraintmap()
            elif command in ("h", "help"):
                cmd_help()
            elif command in ("tsc",):
                cmd_tsc()
            elif command == "tgc":
                cmd_tgc()
            elif command == "tgcdiff":
                cmd_tgc_diff()
            elif command == "reload":
                cmd_reload()
            elif command == "draw":
                cmd_draw()
            # Debug commands
            elif command == "debug":
                cmd_debug()
            elif command == "colors":
                cmd_colors()
            elif command == "gradient":
                cmd_gradient()
            else:
                cmd_unrecognized()

def find_free_filename(before_number: str, after_number: str = "", 
                       prefix = ""):
    """Returns the filename {before_number}{after_number} if not already taken,
    or else returns the filename {before_number}-{i}{after_number} with the 
    smallest i that results in a filename not already taken.
    
    prefix is used to specify a prefix that is applied to the filename
    but is not part of the returned value, used for directory things."""
    incl_number = before_number
    i = 1
    while os.path.exists(prefix + incl_number + after_number):
        incl_number = f"{before_number}-{i}"
        i += 1
    return incl_number + after_number

def extract_layout_front(tokens: Iterable[str], require_full: bool = False):
    """Attempts to find a named layout by joining the tokens with spaces. 
    Returns the layout and remaining tokens. If require_full is set, the
    layout name must take up the entire token."""
    tokens = list(tokens)
    remainder = []
    while tokens:
        try:
            layout_ = layout.get_layout(" ".join(tokens))
            return layout_, remainder
        except OSError:
            if require_full:
                return None, tokens
            else:
                remainder.insert(0, tokens.pop())
    return None, remainder

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

def data_for_tristroke_category(category: str, layout_: layout.Layout, 
        typingdata_: TypingData):
    """Returns (speed: float, num_samples: int, 
    with_fingers: dict[Finger, (speed: float, num_samples: int)],
    without_fingers: dict[Finger, (speed: float, num_samples: int)])
    using the *known* medians in the given tristroke category.

    Note that medians is the output of get_medians_for_layout()."""

    all_samples = []
    speeds_with_fingers = {finger: [] for finger in list(Finger)}
    speeds_without_fingers = {finger: [] for finger in list(Finger)}

    applicable = applicable_function(category)

    for tristroke in typingdata_.exact_tristrokes_for_layout(layout_):
        cat = tristroke_category(tristroke)
        if not applicable(cat):
            continue
        speed = typingdata_.tri_medians[tristroke][2]
        used_fingers = {finger for finger in tristroke.fingers}
        all_samples.append(speed)
        for finger in list(Finger):
            if finger in used_fingers:
                speeds_with_fingers[finger].append(speed)
            else:
                speeds_without_fingers[finger].append(speed)
    
    num_samples = len(all_samples)
    speed = statistics.fmean(all_samples) if num_samples else 0.0
    with_fingers = {}
    without_fingers = {}
    for speeds_l, output_l in zip(
            (speeds_with_fingers, speeds_without_fingers),
            (with_fingers, without_fingers)):
        for finger in list(Finger):
            n = len(speeds_l[finger])
            speed = statistics.fmean(speeds_l[finger]) if n else 0.0
            output_l[finger] = (speed, n)
    
    return (speed, num_samples, with_fingers, without_fingers)

def trigrams_in_list(
        trigrams: Iterable, typingdata_: TypingData, layout_: layout.Layout,
        trigram_freqs: typing.Dict[typing.Tuple[str,...], int]):
    """Returns dict[trigram_tuple, (freq, avg_ms, ms, is_exact)],
    except for the key \"\" which gives (freq, avg_ms, ms, exact_percent)
    for the entire given list."""
    raw = {"": [0, 0, 0]} # total_freq, total_time, known_freq for list
    speed_calc =  typingdata_.tristroke_speed_calculator(layout_)
    for trigram in trigrams:
        try:
            freq = trigram_freqs[trigram]
            tristroke = layout_.to_nstroke(trigram)
        except KeyError:
            continue
        speed, exact = speed_calc(tristroke)
        raw[""][0] += freq
        raw[""][1] += speed*freq
        if exact:
            raw[""][2] += freq
        raw[trigram] = [freq, speed*freq, exact]
    raw[""][2] = raw[""][2]/raw[""][0] if raw[""][0] else 0
    result = dict()
    total_freq = layout_.total_freq(trigram_freqs)
    for key in raw:
        freq = raw[key][0]/total_freq if total_freq else 0
        avg_ms = raw[key][1]/raw[key][0] if raw[key][0] else 0
        ms = raw[key][1]/total_freq if total_freq else 0
        result[key] = (freq, avg_ms, ms, raw[key][2])
    return result

def trigrams_with_specifications_raw(
        typingdata_: TypingData, trigram_freqs: dict, 
        layout_: layout.Layout, category: str,
        with_fingers: set[Finger] = set(Finger), 
        without_fingers: set[Finger] = set()):
    """Returns dict[trigram_tuple, (total_freq, total_time, is_exact)]"""
    applicable = applicable_function(category)
    result = {"": [0, 0, 0]} # total_freq, total_time, known_freq for category
    total_freq = 0 # for all trigrams
    speed_calc =  typingdata_.tristroke_speed_calculator(layout_)
    for trigram, freq in trigram_freqs.items():
        try:
            tristroke = layout_.to_nstroke(trigram)
        except KeyError:
            continue
        total_freq += freq
        if with_fingers.isdisjoint(tristroke.fingers):
            continue
        reject = False
        for finger in tristroke.fingers:
            if finger in without_fingers:
                reject = True
                break
        if reject:
            continue
        cat = tristroke_category(tristroke)
        if not applicable(cat):
            continue
        speed, exact = speed_calc(tristroke)
        result[""][0] += freq
        result[""][1] += speed*freq
        if exact:
            result[""][2] += freq
        result[tuple(trigram)] = [freq, speed*freq, exact]
    return total_freq, result

def trigrams_with_specifications(
        typingdata_: TypingData, trigram_freqs: dict, 
        layout_: layout.Layout, category: str, 
        with_fingers: set[Finger] = set(Finger), 
        without_fingers: set[Finger] = set()):
    """Returns dict[trigram_tuple, (freq, avg_ms, ms, is_exact)],
    except for the key \"\" which gives (freq, avg_ms, ms, exact_percent)
    for the entire given category."""
    total_freq, raw = trigrams_with_specifications_raw(
            typingdata_, trigram_freqs, layout_, category,
            with_fingers, without_fingers)
    raw[""][2] = raw[""][2]/raw[""][0] if raw[""][0] else 0
    result = dict()
    for key in raw:
        freq = raw[key][0]/total_freq if total_freq else 0
        avg_ms = raw[key][1]/raw[key][0] if raw[key][0] else 0
        ms = raw[key][1]/total_freq if total_freq else 0
        result[key] = (freq, avg_ms, ms, raw[key][2])
    return result

def tristroke_breakdowns(medians: dict):
    """Returns a result such that result[category][bistroke] gives
    (speed, num_samples) for bistrokes obtained by breaking down tristrokes
    in that category. 

    This data is useful to estimate the speed of an unknown tristroke by 
    piecing together its component bistrokes, since those may be known.
    """
    samples = {cat: dict() for cat in all_tristroke_categories}
    for ts in medians: # ts is tristroke
        cat = tristroke_category(ts)
        bistrokes = (
            Nstroke(ts.note, ts.fingers[:2], ts.coords[:2]),
            Nstroke(ts.note, ts.fingers[1:], ts.coords[1:])
        )
        for i, b in enumerate(bistrokes):
            speed = medians[ts][i]
            try:
                samples[cat][b].append(speed)
            except KeyError:
                samples[cat][b] = [speed]
    result = {cat: dict() for cat in samples}
    for cat in samples:
        for bs in samples[cat]: # bs is bistroke
            mean = statistics.fmean(samples[cat][bs])
            count = len(samples[cat][bs])
            result[cat][bs] = (mean, count)
    return result

def layout_bistroke_analysis(layout_: layout.Layout, typingdata_: TypingData, 
        bigram_freqs = ...):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    bicatdata is the output of bistroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]
    
    bigram_freqs will be loaded from shai if not specified. 
    (The ability to specify is so you can filter.)"""

    with open("data/shai.json") as file:
        corpus = json.load(file)

    bigram_freqs: typing.Dict[typing.Tuple[str, str], int]
    bigram_freqs = {tuple(k): v for k, v in corpus["bigrams"].items()}
    # {category: [total_time, exact_freq, total_freq]}
    by_category = {category: [0.0,0,0] for category in all_bistroke_categories}
    bi_medians = typingdata_.amalgamated_bistroke_medians(layout_)
    bicatdata = typingdata_.bistroke_category_data(layout_)
    for bigram in bigram_freqs:
        try:
            bistroke = layout_.to_nstroke(bigram)
        except KeyError: # contains key not in layout
            continue
        cat = bistroke_category(bistroke)
        freq = bigram_freqs[bigram]
        if bistroke in bi_medians:
            speed = bi_medians[bistroke]
            by_category[cat][1] += freq
        else:
            speed = bicatdata[cat][0]
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

def layout_tristroke_analysis(layout_: layout.Layout, typingdata_: TypingData,
    trigram_freqs: dict):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    tricatdata is the output of tristroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]
    
    medians is the output of get_medians_for_layout(). That is, 
    dict[Tristroke, (float, float, float)]"""
    # {category: [total_time, exact_freq, total_freq]}
    by_category = {category: [0,0,0] for category in all_tristroke_categories}
    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    for trigram in trigram_freqs:
        try:
            ts = layout_.to_nstroke(trigram)
        except KeyError: # contains key not in layout
            continue
        cat = tristroke_category(ts)
        freq = trigram_freqs[trigram]
        speed, is_exact = speed_func(ts)
        if is_exact:
            by_category[cat][1] += freq
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

def layout_speed(
        layout_: layout.Layout, typingdata_: TypingData,
        trigram_freqs: dict):
    """Like tristroke_analysis but instead of breaking down by category, only
    calculates stats for the "total" category.
    
    Returns (speed, known_prop)"""

    total_freq, known_freq, total_time = layout_speed_raw(
        layout_, typingdata_, trigram_freqs)

    return (total_time/total_freq, known_freq/total_freq)

def layout_speed_raw(
        layout_: layout.Layout, typingdata_: TypingData, trigram_freqs: dict):
    """Returns (total_freq, known_freq, total_time)"""
    total_freq = 0
    known_freq = 0
    total_time = 0
    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    for trigram in trigram_freqs:
        try:
            ts = layout_.to_nstroke(trigram)
        except KeyError: # contains key not in layout
            continue
        freq = trigram_freqs[trigram]
        speed, is_exact = speed_func(ts)
        if is_exact:
            known_freq += freq
        total_time += speed * freq
        total_freq += freq
    return (total_freq, known_freq, total_time)

def finger_analysis(layout_: layout.Layout, typingdata_: TypingData,
        trigram_freqs: dict):
    """Returns dict[finger, (freq, exact, avg_ms, ms)]
    
    finger has possible values including anything in Finger.names, 
    finger_names.values(), and hand_names.values()"""
    # {category: [cat_tfreq, known_tfreq, cat_ttime, lfreq]}
    with open("data/shai.json") as file:
        corpdata = json.load(file)
    letter_freqs = corpdata["letters"]
    total_lfreq = 0
    raw_stats = {finger.name: [0,0,0,0] for finger in Finger}
    raw_stats.update({hand_names[hand]: [0,0,0,0] for hand in hand_names})
    raw_stats.update(
        {finger_names[fingcat]: [0,0,0,0] for fingcat in finger_names})
    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    for key in layout_.keys.values():
        try:
            total_lfreq += letter_freqs[key]
        except KeyError:
            continue
        finger = layout_.fingers[key].name
        raw_stats[finger][3] += letter_freqs[key]
        if finger == Finger.UNKNOWN.name:
            continue
        raw_stats[hand_names[finger[0]]][3] += letter_freqs[key]
        raw_stats[finger_names[finger[1]]][3] += letter_freqs[key]
    total_tfreq = 0
    for trigram in trigram_freqs:
        try:
            tristroke: Tristroke = layout_.to_nstroke(trigram)
        except KeyError: # contains key not in layout
            continue
        tfreq = trigram_freqs[trigram]
        total_tfreq += tfreq
        cats = set()
        for finger in tristroke.fingers:
            cats.add(finger.name)
            if finger != Finger.UNKNOWN:
                cats.add(hand_names[finger.name[0]])
                cats.add(finger_names[finger.name[1]])
        speed, is_exact = speed_func(tristroke)
        for cat in cats:
            if is_exact:
                raw_stats[cat][1] += tfreq
            raw_stats[cat][2] += speed * tfreq
            raw_stats[cat][0] += tfreq
    processed = {}
    for cat in raw_stats:
        processed[cat] = (
            raw_stats[cat][3]/total_lfreq if total_lfreq else 0,
            raw_stats[cat][0]/total_tfreq if total_tfreq else 0, 
            raw_stats[cat][1]/raw_stats[cat][0] if raw_stats[cat][0] else 0,
            raw_stats[cat][2]/raw_stats[cat][0] if raw_stats[cat][0] else 0,
            raw_stats[cat][2]/total_tfreq if total_tfreq else 0, 
        )
    return processed

def key_analysis(layout_: layout.Layout, typingdata_: TypingData,
        trigram_freqs: dict):
    """Like layout_tristroke_analysis but divided up by key.
    Each key only has data for trigrams that contain that key.
    
    Returns a result such that result[key][category] gives 
    (freq_prop, known_prop, speed, contribution)"""
    # {category: [total_time, exact_freq, total_freq]}
    raw = {key: {category: [0,0,0] for category in all_tristroke_categories}
        for key in layout_.keys.values()}

    total_freq = 0

    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    
    for trigram in trigram_freqs:
        try:
            ts = layout_.to_nstroke(trigram)
        except KeyError: # contains key not in layout
            continue
        cat = tristroke_category(ts)
        freq = trigram_freqs[trigram]
        speed, is_exact = speed_func(ts)
        for key in set(trigram):
            if is_exact:
                raw[key][cat][1] += freq
            raw[key][cat][0] += speed * freq
            raw[key][cat][2] += freq
        total_freq += freq
    if not total_freq:
            total_freq = 1
    stats = {key: dict() for key in raw}
    for key in raw:
        # fill in sum categories
        for cat in all_tristroke_categories:
            if not raw[key][cat][2]:
                applicable = applicable_function(cat)
                for othercat in all_tristroke_categories:
                    if raw[key][othercat][2] and applicable(othercat):
                        for i in range(3):
                            raw[key][cat][i] += raw[key][othercat][i]
        # process stats
        for cat in all_tristroke_categories:
            cat_freq = raw[key][cat][2]
            if not cat_freq:
                cat_freq = 1
            freq_prop = raw[key][cat][2] / total_freq
            known_prop = raw[key][cat][1] / cat_freq
            cat_speed = raw[key][cat][0] / cat_freq
            contribution = raw[key][cat][0] / total_freq
            stats[key][cat] = (freq_prop, known_prop, cat_speed, contribution)
    
    return stats

def steepest_ascent(layout_: layout.Layout, typingdata_: TypingData,
        trigram_freqs: dict, constraintmap_: Constraintmap, 
        pins: Iterable[str] = tuple(), suffix: str = "-ascended"):
    """Yields (newlayout, score, swap_made) after each step.
    """
    lay = layout.Layout(layout_.name, False, repr(layout_))
    if not lay.name.endswith(suffix):
        lay.name += suffix
    lay.name = find_free_filename(lay.name, prefix="layouts/")
    
    swappable = set(lay.keys.values())
    for key in pins:
        swappable.discard(key)

    total_freq, known_freq, total_time = layout_speed_raw(
        lay, typingdata_, trigram_freqs
    )

    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    speed_dict = {ts: speed_func(ts) for ts in lay.all_nstrokes()}

    with open("data/shai.json") as file:
        corp_data = json.load(file)
    lfreqs = corp_data["letters"]
    total_lfreq = sum(lfreqs[key] for key in layout_.positions
        if key in lfreqs)
    for key in lfreqs:
        lfreqs[key] /= total_lfreq
        
    scores = [total_time/total_freq]
    rows = tuple({pos.row for pos in lay.keys})
    cols = tuple({pos.col for pos in lay.keys})
    swaps = tuple(remap.swap(pair) for pair in itertools.combinations(swappable, 2))
    with multiprocessing.Pool(4) as pool:
        while True:            
            row_swaps = (remap.row_swap(lay, r1, r2, pins) 
                for r1, r2 in itertools.combinations(rows, 2))
            col_swaps = (remap.col_swap(lay, c1, c2, pins) 
                for c1, c2 in itertools.combinations(cols, 2))

            args = (
                (remap, total_freq, known_freq, total_time, lay,
                    trigram_freqs, speed_dict)
                for remap in itertools.chain(swaps, row_swaps, col_swaps)
                if constraintmap_.is_remap_legal(lay, lfreqs, remap))
            datas = pool.starmap(remapped_score, args, 200)
            try:
                best = min(datas, key=lambda d: d[2]/d[0])
            except ValueError:
                return # no swaps exist
            best_remap = best[3]
            best_score = best[2]/best[0]

            if best_score < scores[-1]:
                total_freq, known_freq, total_time = best[:3]
                scores.append(best_score)
                lay.remap(best_remap)
                
                yield lay, scores[-1], best_remap
            else:
                return # no swaps are good

def remapped_score(
        remap_: Remap, total_freq, known_freq, total_time,
        lay: layout.Layout, trigram_freqs: dict, 
        speed_func: typing.Union[Callable, dict]):
    # swaps should be length 2
    """(total_freq, known_freq, total_time, remap)"""
    
    for ngram in lay.ngrams_with_any_of(remap_):
        try:
            tfreq = trigram_freqs[ngram]
        except KeyError: # contains key not in corpus
            continue
        
        # remove effect of original tristroke
        ts = lay.to_nstroke(ngram)
        try:
            speed, is_known = speed_func(ts)
        except TypeError:
            speed, is_known = speed_func[ts]
        if is_known:
            known_freq -= tfreq
        total_time -= speed * tfreq
        total_freq -= tfreq
        
        # add effect of swapped tristroke
        ts = lay.to_nstroke(remap_.translate(ngram))
        try:
            speed, is_known = speed_func(ts)
        except TypeError:
            speed, is_known = speed_func[ts]
        if is_known:
            known_freq += tfreq
        total_time += speed * tfreq
        total_freq += tfreq
    
    return (total_freq, known_freq, total_time, remap_)

def anneal(layout_: layout.Layout, typingdata_: TypingData,
        trigram_freqs: dict, constraintmap_: Constraintmap,
        pins: Iterable[str] = tuple(), suffix: str = "-annealed",
        iterations: int = 10000):
    """Yields (layout, i, temperature, delta, score, remap) 
    when a remap is successful."""
    lay = layout.Layout(layout_.name, False, repr(layout_))
    if not lay.name.endswith(suffix):
        lay.name += suffix

    total_freq, known_freq, total_time = layout_speed_raw(
        lay, typingdata_, trigram_freqs
    )

    speed_func = typingdata_.tristroke_speed_calculator(layout_)

    with open("data/shai.json") as file:
        corp_data = json.load(file)
    lfreqs = corp_data["letters"]
    total_lfreq = sum(lfreqs[key] for key in layout_.positions
        if key in lfreqs)
    for key in lfreqs:
        lfreqs[key] /= total_lfreq
    
    scores = [total_time/total_freq]
    T0 = 10
    Tf = 1e-3
    k = math.log(T0/Tf)

    rows = tuple({pos.row for pos in lay.keys})
    cols = tuple({pos.col for pos in lay.keys})
    remap_ = Remap()

    random.seed()
    for i in range(iterations):
        temperature = T0*math.exp(-k*i/iterations)
        try_rowswap = i % 100 == 0
        if try_rowswap:
            remap_ = remap.row_swap(lay, *random.sample(rows, 2), pins)
        try_colswap = ((not try_rowswap) and i % 10 == 0
            or try_rowswap and not constraintmap_.is_remap_legal(
                lay, lfreqs, remap_))
        if try_colswap:
            remap_ = remap.col_swap(lay, *random.sample(cols, 2), pins)
        if (
                not (try_colswap or try_rowswap) or 
                (try_colswap or try_rowswap) and not 
                    constraintmap_.is_remap_legal(lay, lfreqs, remap_)):
            remap_ = constraintmap_.random_legal_swap(lay, lfreqs, pins)
        data = remapped_score(remap_, total_freq, known_freq, total_time,
            lay, trigram_freqs, speed_func)
        score = data[2]/data[0]
        delta = score - scores[-1]

        if score > scores[-1]:
            p = math.exp(-delta/temperature)
            if random.random() > p:
                continue

        total_freq, known_freq, total_time = data[:3]
        scores.append(score)
        lay.remap(remap_)
        
        yield lay, i, temperature, delta, scores[-1], remap_
    return
    
if __name__ == "__main__":
    curses.wrapper(main)
