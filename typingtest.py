import operator
import time
import queue
import statistics
import curses
from typing import Collection
from pynput import keyboard

import nstroke
import layout
import gui_util
from corpus import default_lower, default_upper
import session

key_events = queue.Queue()

def on_press(key):
    global key_events
    key_events.put((key, time.perf_counter_ns()))

def on_release(key):
    if key == keyboard.Key.esc:
        # Listener stops when False returned
        return False

def wpm(ms) -> int:
    """Returns the wpm conversion given the time taken to type a *bigram*. 
    For a trigram, multiply this result by 2.
    For a quadgram, multiply this result by 3, etc.
    """
    return int(12000/ms)

shift_aliases = set(
    frozenset(pair) for pair in zip(default_lower, default_upper))

def test(s: session.Session, tristroke: nstroke.Tristroke,
         estimate: float = None):
    """Run a typing test with the specified tristroke.
    The new data is saved into s.typingdata_.csv_data.
    """

    curses.curs_set(0)

    s.right_pane.clear()
    s.right_pane.addstr(1, 0, "Typing test - Press esc to finish")

    height, width = s.right_pane.getmaxyx()
    stats_win_height = 14
    if estimate is not None:
        stats_win_height += 1
    stats_win = s.right_pane.derwin(stats_win_height, width, 2, 0)
    message_win = s.right_pane.derwin(stats_win_height, 0)

    def message(msg: str, color: int = 0): # mostly for brevity
        gui_util.insert_line_bottom(
            msg, message_win, curses.color_pair(color))
        message_win.refresh()

    trigram = s.user_layout.to_ngram(tristroke)
    if not trigram:
        message("User layout does not have a trigram for the specified "
            "tristroke\nExiting!", gui_util.red)
    
    valid_keys = set(trigram)
    all_aliases = shift_aliases.union(s.key_aliases)
    for key in trigram:
        for set_ in all_aliases:
            if key in set_:
                valid_keys.update(set_)

    fingers = tuple(f.name for f in tristroke.fingers)

    stats_win.hline(0, 0, "-", width-2)
    stats_win.addstr(1, 0, "Bigram {} {} ({}, {}): {}".format(
        *trigram[:2], *fingers[:2], nstroke.bistroke_category(tristroke, 0, 1)))
    stats_win.addstr(2, 0, "mean / stdev / median")
    stats_win.hline(4, 0, "-", width-2)
    stats_win.addstr(5, 0, "Bigram {} {} ({}, {}): {}".format(
        *trigram[1:], *fingers[1:], nstroke.bistroke_category(tristroke, 1, 2)))
    stats_win.addstr(6, 0, "mean / stdev / median")
    stats_win.hline(8, 0, "-", width-2)
    stats_win.addstr(9, 0, "Trigram " + " ".join(trigram) + 
        " ({}, {}, {}): {}".format(
            *fingers, nstroke.tristroke_category(tristroke)))
    stats_win.addstr(10, 0, "mean / stdev / median")
    if estimate is not None:
        stats_win.addstr(12, 0, f"Previous estimate: {estimate:.2f} ms")

    def format_stats(data: list):
        try:
            return "{0:^5.1f}   {1:^5.1f}   {2:^5.1f} ms, n={3}".format(
                statistics.fmean(data),
                statistics.stdev(data),
                statistics.median(data),
                len(data)
            )
        except statistics.StatisticsError:
            return "Not enough data, n={0}".format(len(data))

    last_time = time.perf_counter_ns()
    next_index = 0
    if tristroke not in s.typingdata_.csv_data:
        s.typingdata_.csv_data[tristroke] = ([], [])
    speeds_01 = s.typingdata_.csv_data[tristroke][0]
    speeds_12 = s.typingdata_.csv_data[tristroke][1]
    speeds_02 = list(map(operator.add, speeds_01, speeds_12))

    pynput_listener = keyboard.Listener(on_press=on_press,
                                        on_release=on_release)
    pynput_listener.start()
    pynput_listener.wait()
    global key_events
    while pynput_listener.running:
        time.sleep(0.02)
        # process key events
        while not key_events.empty():
            key, new_time = key_events.get()
            try:
                key_name = key.char
            except AttributeError:
                key_name = key                
            if str(key_name).startswith("Key."):
                key_name = str(key_name)[4:]

            key_correct = False
            for set_ in all_aliases:
                if trigram[next_index] in set_ and key_name in set_:
                    key_correct = True
                    break

            if key_name == trigram[next_index]:
                key_correct = True

            if not key_correct:
                if key_name == "esc":
                    message("Finishing test", gui_util.green)
                elif key_name in valid_keys:
                    message("Key " + key_name + 
                                " out of sequence, trigram invalidated",
                            gui_util.red)
                    next_index = 0
                    if len(speeds_01) != len(speeds_12):
                        speeds_01.pop()
                else:
                    message("Ignoring wrong key " + key_name, gui_util.red)
                continue

            # Key is correct, proceed
            bigram_ms = (new_time - last_time)/1e6
            if next_index == 0: # first key just typed
                message("First key detected", gui_util.blue)
            elif next_index == 1: # second key just typed
                speeds_01.append(bigram_ms)
                message("Second key detected after {0:.1f} ms".format(bigram_ms),
                        gui_util.blue)
            else: # trigram just completed
                speeds_12.append(bigram_ms)
                speeds_02.append(bigram_ms + speeds_01[-1])
                message("Trigram complete, took {0:.1f} ms ({1} wpm)"
                            .format(speeds_02[-1], 2*wpm(speeds_02[-1])),
                        gui_util.green)

            next_index = (next_index + 1) % 3
            last_time = new_time
            key_events.task_done()
        
        for line in (3, 7, 11):
            stats_win.move(line, 0)
            stats_win.clrtoeol()
        stats_win.addstr(3, 0, format_stats(speeds_01))
        stats_win.addstr(7, 0, format_stats(speeds_12))
        stats_win.addstr(11, 0, format_stats(speeds_02))

        stats_win.refresh()
        s.right_pane.refresh()
        s.right_pane.move(height-1, 0)

    if not speeds_01 or not speeds_12:
        del s.typingdata_.csv_data[tristroke]

    s.right_pane.refresh()
    curses.flushinp()
    curses.curs_set(1)