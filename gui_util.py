import curses

def insert_line_bottom(text: str, window: curses.window, attr: int = ...):
    """Scrolls a line in from the bottom of the window. 
    Wraps overflow onto subsequent lines.
    Does not refresh the window.
    """
    ymax, xmax = window.getmaxyx()

    while len(text) > xmax-1:
        first_line = text[:xmax-1]
        text = text[xmax-1:]
        insert_line_bottom(first_line, window, attr)

    # window.move(0,0)
    # window.deleteln()
    window.scrollok(True)
    window.idlok(True)
    window.scroll(1)

    if attr != ...:
        window.addstr(ymax-1, 0, text, attr)
    else:
        window.addstr(ymax-1, 0, text)

def debug_win(window: curses.window, label: str):
    window.border()
    for i in range(window.getmaxyx()[0]):
        window.addstr(i, 0, str(i) + " ")
    window.addstr(0, 0, label + " 0,0")
    window.refresh()