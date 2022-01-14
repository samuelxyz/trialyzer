import curses

red = 1
green = 2
blue = 3
gray = 4

gradient_colors = (196, 202, 208, 214, 220, 226, 190, 154, 118, 82, 46)

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    bg = -1
    # bg = curses.COLOR_BLACK
    curses.init_pair(red, curses.COLOR_RED, bg)
    curses.init_pair(green, curses.COLOR_GREEN, bg)
    curses.init_pair(blue, curses.COLOR_CYAN, bg)
    curses.init_pair(gray, 244, bg)

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
        curses.init_pair(i, i, bg)

def color_scale(worst, best, target, exclude_zeros = False):
    """Make sure to run the result through curses.color_pair()."""
    if exclude_zeros and not target: return gray
    if best == worst:
        if target > best: return gradient_colors[-1]
        elif target < best: return gradient_colors[0]
        else: return gradient_colors[int(len(gradient_colors)/2)]
    fraction = (target-worst) / (best-worst)
    if fraction < 0:
        fraction = 0
    elif fraction >= 1.0:
        fraction = 0.999
    i = int(len(gradient_colors)*fraction)
    return gradient_colors[i]

def insert_line_bottom(text: str, win: curses.window, attr: int = ...):
    """Scrolls a line in from the bottom of the window. 
    Wraps overflow onto subsequent lines.
    Does not refresh the window.
    """
    if "\n" in text:
        for subtext in text.split("\n"):
            insert_line_bottom(subtext, win, attr)
        return
    
    ymax, xmax = win.getmaxyx()

    while len(text) > xmax-1:
        first_line = text[:xmax-1]
        text = text[xmax-1:]
        insert_line_bottom(first_line, win, attr)

    # win.scrollok(True)
    # win.idlok(True)
    win.scroll(1)

    if attr != ...:
        win.addstr(ymax-1, 0, text, attr)
    else:
        win.addstr(ymax-1, 0, text)

def debug_win(win: curses.window, label: str):
    win.border()
    for i in range(win.getmaxyx()[0]):
        win.addstr(i, 0, str(i) + " ")
    win.addstr(0, 0, label + " 0,0")
    win.refresh()