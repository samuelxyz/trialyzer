import typingtest
import curses

def main(stdscr: curses.window):
    curses.curs_set(False)
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)
    stdscr.addstr("test of the test", curses.color_pair(1))
    stdscr.addstr(1, 0, "Press esc to exit")
    stdscr.refresh()
    typingtest.test(stdscr)

if __name__ == "__main__":
    curses.wrapper(main)