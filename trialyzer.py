import typingtest
import curses
import curses.textpad
import layout
import gui_util

def draw_main(content: curses.window, text: str):
    content.refresh()

def main(stdscr: curses.window):
    curses.curs_set(0)

    height, width = stdscr.getmaxyx()
    titlebar = stdscr.subwin(1,width,0,0)
    content_win = stdscr.subwin(1, 0)

    startup_text = [
            "Commands:",
            "[t]ype <trigram>: Enter typing test",
            "[l]ayout <layout name>: Load layout",
            "[d]ebug: Draw a box around the message window (curses moment lmao)",
            "[q]uit"]

    height, width = content_win.getmaxyx()
    input_win = content_win.derwin(height-2, 1)
    input_box = curses.textpad.Textbox(input_win, True)
    message_win = content_win.derwin(height-len(startup_text)-2, width, len(startup_text), 0)
    # gui_util.debug_win(content_win, "content_win")
    # gui_util.debug_win(message_win, "message_win")
    
    titlebar.bkgdset(" ", curses.A_REVERSE)
    titlebar.addstr("Trialyzer")
    titlebar.refresh()

    red_pair = 1
    curses.init_pair(red_pair, curses.COLOR_RED, curses.COLOR_BLACK)
    green_pair = 2
    curses.init_pair(green_pair, curses.COLOR_GREEN, curses.COLOR_BLACK)
    active_layout = layout.get_layout("qwerty")

    while True:
        content_win.addstr(0, 0, "\n".join(startup_text))
        content_win.addch(height-2, 0, ">")
        content_win.refresh()
        input_win.clear()
        input_win.refresh()
        input_win.move(0,0)
        curses.curs_set(1)
        input_str = input_box.edit()
        input_win.clear()
        gui_util.insert_line_bottom(">" + input_str, message_win)
        message_win.refresh()
        args = input_str.split()
        if not len(args):
            continue
        command = args.pop(0).lower()

        if command in ("q", "quit"):
            return
        elif command in ("t", "type"):
            if len(args[0]) == 3:
                typingtest.test(content_win, args[0], active_layout)
            elif len(args) == 3:
                typingtest.test(content_win, args, active_layout)
            input_win.clear()
        elif command in ("l", "layout"):
            layout_name = " ".join(args)
            if layout_name:
                try:
                    active_layout = layout.get_layout(layout_name)
                    gui_util.insert_line_bottom("Set " + layout_name + " as the active layout.", message_win, curses.color_pair(green_pair))
                except OSError:
                    gui_util.insert_line_bottom("That layout was not found.", message_win, curses.color_pair(red_pair))
                message_win.refresh()
        elif command in ("d", "debug"):
            gui_util.debug_win(message_win, "message_win")

if __name__ == "__main__":
    curses.wrapper(main)