import curses

red = 1
green = 2
blue = 3
gray = 4

gradient_colors = (196, 202, 208, 214, 220, 226, 190, 154, 118, 82, 46)

def init_colors():
    curses.start_color()
    curses.init_pair(red, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(green, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(blue, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(gray, 244, curses.COLOR_BLACK)

    # n = gradient_colors + 8
    # m = min_gradient_color - 4
    # for i in range(n): # colors for worst to best
    #     curses.init_color(
    #         m+i, 
    #         int(1000*(1-i/n)), 
    #         int(1000*(1-2*abs(i/n-0.5))), 
    #         int(1000*(i/n))
    #     )
        # curses.init_pair(m+i, m+i, curses.COLOR_BLACK)

    for i in range(5, curses.COLOR_PAIRS):
        curses.init_pair(i, i, curses.COLOR_BLACK)

def color_scale(worst, best, target, exclude_zeros = False):
    """Make sure to run the result through curses.color_pair()."""
    if exclude_zeros and not target: return gray
    fraction = (target-worst) / (best-worst)
    if fraction >= 1.0:
        fraction = 0.999
    i = int(len(gradient_colors)*fraction)
    return gradient_colors[i]

def insert_line_bottom(text: str, window: curses.window, attr: int = ...):
    """Scrolls a line in from the bottom of the window. 
    Wraps overflow onto subsequent lines.
    Does not refresh the window.
    """
    if "\n" in text:
        for subtext in text.split("\n"):
            insert_line_bottom(subtext, window, attr)
        return
    
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