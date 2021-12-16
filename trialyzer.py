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

    def message(msg: str, color: int = 0): # mostly for brevity
        gui_util.insert_line_bottom(
            msg, message_win, curses.color_pair(color))
        message_win.refresh()

    while True:
        content_win.addstr(0, 0, "\n".join(startup_text))
        content_win.addstr(height-2, 0, "> ")
        content_win.refresh()

        input_win.clear()
        input_win.refresh()
        input_win.move(0,0)
        curses.curs_set(1)

        input_str = input_box.edit()

        input_win.clear()
        input_win.refresh()
        message("> " + input_str)

        args = input_str.split()
        if not len(args):
            continue
        command = args.pop(0).lower()

        if command in ("q", "quit"):
            return
        elif command in ("t", "type"):
            if len(args[0]) == 3:
                trigram = args[0]
            elif len(args) == 3:
                trigram = args
            else:
                trigram = "abc" # TODO: Automatically pick a trigram
            message("Starting typing test >>>", text_green)
            typingtest.test(right_pane, trigram, active_layout)
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

if __name__ == "__main__":
    curses.wrapper(main)