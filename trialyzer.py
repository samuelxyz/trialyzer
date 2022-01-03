import csv
import itertools
import operator
import statistics
from os import path

from board import Coord
from fingermap import Finger
from nstroke import *
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
            "bs|bistrokes [csvname]: Show applicable bistroke stats",
            "ts|tristrokes [csvname]: Show applicable tristroke stats",
            "tc <category> [csvname]: Show stats for tristroke category",
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

    def print_stroke_categories(data: dict, counts = None):
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
            display_out = (
                    "{:" + pad_char + "<26} {:>6.1f}   {:< 6}"
                ).format(
                    category_name, float(data[category][0]), 
                    data[category][1]
                )
            if counts:
                display_out += "/{:<6}".format(counts[category])
            gui_util.insert_line_bottom(display_out, right_pane)
        
        right_pane.refresh()

    def csv_exists(filename: str):
        good = path.exists("data/" + filename + ".csv")
        if not good:
            if filename == "default":
                message("No csv data was found.", text_red) 
            else:   
                message("That csv was not found.", text_red)
        return good
   
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
                tristroke: Tristroke = entry[0]
                if tristroke not in data:
                    data[tristroke] = ([],[])
                data[tristroke][0].extend(entry[1][0])
                data[tristroke][1].extend(entry[1][1])
            unsaved_typingtest_data.clear()
            save_csv_data(data, filename)
            message("Data saved", text_green)
        elif command in ("bs", "bistrokes"):
            if not args:
                filename = "default"
            else:
                filename = " ".join(args)
            if not csv_exists(filename):
                continue
            message("Crunching the numbers >>>", text_green)
            message_win.refresh()
            right_pane.clear()
            data = bistroke_category_data(get_medians_for_layout(
                load_csv_data(filename), active_layout))
            print_stroke_categories(data)
        elif command in ("ts", "tristrokes"):
            if not args:
                filename = "default"
            else:
                filename = " ".join(args)
            if not csv_exists(filename):
                continue
            message("Crunching the numbers >>>", text_green)
            right_pane.clear()
            data = tristroke_category_data(get_medians_for_layout(
                load_csv_data(filename), active_layout))
            header_line = "Category                       ms    n"
            gui_util.insert_line_bottom(header_line, right_pane)
            active_layout.preprocessors["counts"].join()
            print_stroke_categories(data, active_layout.counts)
        elif command in ("tc",):
            filename = "default"
            if not args:
                category_name = ""
            else:
                category_name = args[0].lower().strip()
                if len(args) >= 2:
                    filename = args[1]
            if not csv_exists(filename):
                continue

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
                message("Unrecognized category", text_red)
                continue
            
            message("Crunching the numbers >>>", text_green)
            (speed, num_samples, with_fingers, without_fingers
            ) = data_for_tristroke_category(category, get_medians_for_layout(
                load_csv_data(filename), active_layout
            ))
            display_name = (category_display_names[category] 
                if category in category_display_names else category)
            gui_util.insert_line_bottom(
                ("\nTristroke category: {}\nAverage ""{:.2f} ms, n={}\n")
                    .format(display_name, speed, num_samples),
                right_pane)
            spacing = 5
            indent = 17
            lh_fingers = tuple(
                finger.name for finger in reversed(sorted(Finger)) if finger < 0)
            rh_fingers = tuple(
                finger.name for finger in sorted(Finger) if finger > 0)
            lh_fingers_label = " " * indent + (" " * spacing).join(lh_fingers)
            rh_fingers_label = " " * indent + (" " * spacing).join(rh_fingers)
            dash = "-" * len(lh_fingers_label)
            speeds_left = "speeds (ms): " + " ".join(("{:>6.1f}".format(
                with_fingers[Finger[finger]][0]) for finger in lh_fingers
            ))
            n_left = "       n = : " + " ".join(("{:>6}".format(
                with_fingers[Finger[finger]][1]) for finger in lh_fingers
            ))
            speeds_right = "speeds (ms): " + " ".join(("{:>6.1f}".format(
                with_fingers[Finger[finger]][0]) for finger in rh_fingers
            ))
            n_right = "       n = : " + " ".join(("{:>6}".format(
                with_fingers[Finger[finger]][1]) for finger in rh_fingers
            ))
            gui_util.insert_line_bottom("\n".join((
                "With finger:", dash,
                lh_fingers_label, speeds_left, n_left, dash,
                rh_fingers_label, speeds_right, n_right, dash,
                "")), right_pane)
            speeds_left = "speeds (ms): " + " ".join(("{:>6.1f}".format(
                without_fingers[Finger[finger]][0]) for finger in lh_fingers
            ))
            n_left = "       n = : " + " ".join(("{:>6}".format(
                without_fingers[Finger[finger]][1]) for finger in lh_fingers
            ))
            speeds_right = "speeds (ms): " + " ".join(("{:>6.1f}".format(
                without_fingers[Finger[finger]][0]) for finger in rh_fingers
            ))
            n_right = "       n = : " + " ".join(("{:>6}".format(
                without_fingers[Finger[finger]][1]) for finger in rh_fingers
            ))
            gui_util.insert_line_bottom("\n".join((
                "Without finger:", dash,
                lh_fingers_label, speeds_left, n_left, dash,
                rh_fingers_label, speeds_right, n_right, dash)),
                right_pane)
            right_pane.refresh()
        else:
            message("Unrecognized command", text_red)            

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
    
if __name__ == "__main__":
    curses.wrapper(main)