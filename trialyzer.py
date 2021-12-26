import csv
import itertools

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
            "[d]ebug: Draw a box around the message window "
                "(curses moment lmao)",
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
    unsaved_tristroke_data = []

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
            if unsaved_tristroke_data:
                message("Quit without saving? (y/n)", text_blue)
                if get_input().strip().lower() in ("y", "yes"):
                    return
                else:
                    continue
            return
        elif command in ("t", "type"):
            if not args:
                trigram = "abc" # TODO: Automatically pick a trigram
            elif len(args[0]) == 3:
                trigram = [char for char in args[0]]
            elif len(args) == 3:
                trigram = args
            else:
                message("Malformed trigram", text_red)
                continue
            message("Starting typing test >>>", text_green)
            unsaved_tristroke_data.append(
                (active_layout.to_tristroke(trigram),
                    typingtest.test(right_pane, trigram, active_layout))
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
            if not args:
                filename = "default"
            else:
                filename = " ".join(args)
            header = [
                "note", "finger1", "finger2", "finger3",
                "x1", "y1", "x2", "y2", "x3", "y3"
            ]
            # TODO: load existing data and merge with unsaved
            with open("data/" + filename + ".csv", "w", newline="") as csvfile:
                w = csv.writer(csvfile)
                w.writerow(header)
                for entry in unsaved_tristroke_data:
                    row = start_writable_row(entry[0])
                    row.extend(itertools.chain.from_iterable(
                        zip(entry[1][0], entry[1][1])))
                    w.writerow(row)
            unsaved_tristroke_data.clear()
            message("Data saved", text_green)

def start_writable_row(tristroke: layout.Tristroke):
    """Order of returned data: note, fingers, coords"""
    
    result = [tristroke.note]
    result.extend(f.name for f in tristroke.fingers)
    result.extend(itertools.chain.from_iterable(tristroke.coords))
    return result

if __name__ == "__main__":
    curses.wrapper(main)