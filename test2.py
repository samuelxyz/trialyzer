import curses

import command
from session import Session

def main(stdscr: curses.window):
    session_ = Session(stdscr)
    while True:
        for name, args in session_.prompt_user_command():
            if command.run_command(name, args, session_) == "quit":
                return

if __name__ == "__main__":
    curses.wrapper(main)
