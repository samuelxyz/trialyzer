import json
import curses
import curses.textpad
import math

import constraintmap
import gui_util
import layout
from typingdata import TypingData


class Session:
    """
    Contains trialyzer settings, data, and interface elements--everything 
    needed for commands to be run.
    """

    def __init__(self, stdscr: curses.window) -> None:
        self.startup_messages = []
    
        try:
            with open("session_settings.json") as settings_file:
                settings = json.load(settings_file)
            some_default = False
            try:
                self.analysis_target = layout.get_layout(
                    settings["analysis_target"])
            except (FileNotFoundError, KeyError):
                self.analysis_target = layout.get_layout("qwerty")
                some_default = True
            try:
                self.user_layout = layout.get_layout(settings["user_layout"])
            except (FileNotFoundError, KeyError):
                self.user_layout = layout.get_layout("qwerty")
                some_default = True
            try:
                self.speeds_file = settings["active_speeds_file"]
            except KeyError:
                self.speeds_file = "default"
                some_default = True
            try:
                self.constraintmap_ = constraintmap.get_constraintmap(
                    settings["constraintmap"])
            except (KeyError, FileNotFoundError):
                self.constraintmap_ = constraintmap.get_constraintmap(
                    "traditional-default")
                some_default = True
            try:
                self.key_aliases = set(
                    frozenset(keys) for keys in settings["key_aliases"])
            except KeyError:
                self.key_aliases = set()
            try:
                self.corpus_settings = settings["corpus_settings"]
            except KeyError:
                self.corpus_settings = {
                    "filename": "tr_quotes.txt",
                    "space_key": "space",
                    "shift_key": "shift",
                    "shift_policy": "once",
                    "precision": 500,
                }
                some_default = True
            self.startup_messages.append(("Loaded user settings", gui_util.green))
            if some_default:
                self.startup_messages.append((
                    "Set some missing/bad settings to default", gui_util.blue))
        except (FileNotFoundError, KeyError, json.decoder.JSONDecodeError):
            self.speeds_file = "default"
            self.analysis_target = layout.get_layout("qwerty")
            self.user_layout = layout.get_layout("qwerty")
            self.constraintmap_ = constraintmap.get_constraintmap(
                "traditional-default")
            self.key_aliases = set()
            self.corpus_settings = {
                "filename": "tr_quotes.txt",
                "space_key": "space",
                "shift_key": "shift",
                "shift_policy": "once",
                "precision": 500,
            }
            self.startup_messages.append(
                ("Using default user settings", gui_util.red))

        self.typingdata_ = TypingData(self.speeds_file)
        self.target_corpus = self.analysis_target.get_corpus(
            self.corpus_settings)

        self.save_settings()

        curses.curs_set(0)
        gui_util.init_colors()

        self.height, self.twidth = stdscr.getmaxyx()
        self.titlebar = stdscr.subwin(1,self.twidth,0,0)
        self.titlebar.bkgd(" ", curses.A_REVERSE)
        self.titlebar.addstr("Trialyzer" + " "*(self.twidth-10))
        self.titlebar.refresh()
        self.content_win = stdscr.subwin(1, 0)

        self.height, self.twidth = self.content_win.getmaxyx()
        self.header_lines = math.ceil(len(self.header_text())/2)
        self.repl_win = self.content_win.derwin(
            self.height-self.header_lines-2, int(self.twidth/3), 
            self.header_lines, 0
        )
        self.right_pane = self.content_win.derwin(
            self.height-self.header_lines-2, int(self.twidth*2/3), 
            self.header_lines, int(self.twidth/3)
        )
        for win in (self.repl_win, self.right_pane):
            win.scrollok(True)
            win.idlok(True)
        self.input_win = self.content_win.derwin(self.height-2, 2)
        self.input_box = curses.textpad.Textbox(self.input_win, True)        

        for item in self.startup_messages:
            self.say(*item)

        self.last_command = ""
        self.last_args = []

    def prompt_user_command(self):
        """Yields (command_name, args). This is a generator because some 
        user inputs cause commands to be run multiple times. Returns
        immediately if the user input is blank."""

        self.content_win.addstr(self.height-2, 0, "> ")
        self.print_header()

        self.input_win.clear()
        self.input_win.refresh()

        input_args = self.get_input().split()
        if not len(input_args):
            return
        command = input_args.pop(0).lower()
        try:
            num_repetitions = int(command)
            command = input_args.pop(0).lower()
        except ValueError:
            num_repetitions = 1
        
        if command in (".",):
            command = self.last_command
            input_args = self.last_args
        else:
            self.last_command = command
            self.last_args = input_args.copy()

        if not command:
            return
        
        for _ in range(num_repetitions):
            yield command, input_args.copy()

    def save_settings(self):
        with open("session_settings.json", "w") as settings_file:
            json.dump(
                {   "analysis_target": self.analysis_target.name,
                    "user_layout": self.user_layout.name,
                    "active_speeds_file": self.speeds_file,
                    "constraintmap": self.constraintmap_.name,
                    "corpus_settings": self.corpus_settings,
                    "key_aliases": [tuple(keys) for keys in self.key_aliases]
                }, settings_file)
            
    def header_text(self): 
        precision_text = (
            f"all ({len(self.target_corpus.top_trigrams)})" 
                if not self.target_corpus.precision
                else f"top {self.target_corpus.precision}"
        )
        space_string = (self.corpus_settings['space_key'] 
                        if self.corpus_settings['space_key'] else "[don't analyze spaces]")
        shift_string = (self.corpus_settings['shift_key'] 
                        if self.corpus_settings['shift_key'] else "[don't analyze shift]")
        text = [
            "\"h\" or \"help\" to show command list",
            f"Analysis target: {self.analysis_target}",
            f"User layout: {self.user_layout}",
            f"Active speeds file: {self.speeds_file}"
            f" (/data/{self.speeds_file}.csv)",
            f"Generation constraintmap: {self.constraintmap_.name}",
            f"Corpus: {self.corpus_settings['filename']}",
            f"Default space key: {space_string}",
            f"Default shift key: {shift_string}",
        ]
        if self.corpus_settings["shift_key"]:
            text.append("Consecutive capital letters: shift "
                f"{self.corpus_settings['shift_policy']}")
        text.append(
            f"Precision: {precision_text} "
                f"({self.target_corpus.trigram_completeness:.3%})"
        )
        return text
    
    def print_header(self):
        for i in range(self.header_lines):
            self.content_win.move(i, 0)
            self.content_win.clrtoeol()
        header_text_ = self.header_text()
        second_col_start = 3 + max(
            len(line) for line in header_text_[:self.header_lines])
        second_col_start = max(second_col_start, int(self.twidth/3))
        for i in range(self.header_lines):
            self.content_win.addstr(i, 0, header_text_[i])
        for i in range(self.header_lines, len(header_text_)):
            self.content_win.addstr(
                i-self.header_lines, second_col_start, header_text_[i])
        
        self.content_win.refresh()

    def say(self, msg: str, color: int = 0, 
                win: curses.window = ...):
        if win == ...:
            win = self.repl_win
        gui_util.insert_line_bottom(
            msg, win, curses.color_pair(color))
        win.refresh()

    def output(self, msg: str, color: int = 0):
        self.say(msg, color, win=self.right_pane)

    def get_input(self) -> str:
        self.input_win.move(0,0)
        curses.curs_set(1)

        res = self.input_box.edit()

        self.input_win.clear()
        self.input_win.refresh()
        self.say("> " + res)
        return res
