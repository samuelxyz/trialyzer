import curses

def insert_line_bottom(str, window: curses.window, attr: int = ...):
    window.move(0,0)
    window.deleteln()
    ymax, xmax = window.getmaxyx()
    if attr != ...:
        window.addnstr(ymax-1, 0, str, xmax-1, attr)
    else:
        window.addnstr(ymax-1, 0, str, xmax-1)

def debug_win(window: curses.window, label: str):
    window.border()
    for i in range(window.getmaxyx()[0]):
        window.addstr(i, 0, str(i) + " ")
    window.addstr(0, 0, label + " 0,0")
    window.refresh()