import time
import queue
import statistics

import curses
from typing import Iterable
from pynput import keyboard

import layout
import gui_util

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

def test(window: curses.window, trigram: Iterable[str], active_layout: layout.Layout):
    """Run a typing test with the specified trigram.

    trigram is a list of three key names.
    """

    curses.curs_set(0)

    window.clear()
    window.addstr(0, 0, "Typing test - Press esc to finish")

    height, width = window.getmaxyx()
    stats_win = window.derwin(13, width, 1, 0)
    message_win = window.derwin(13, 0)

    stats_win.hline(0, 0, "-", width-2)
    stats_win.addstr(1, 0, "Bigram " + trigram[0] + " " + trigram[1])
    stats_win.addstr(2, 0, "mean / stdev / median")
    stats_win.hline(4, 0, "-", width-2)
    stats_win.addstr(5, 0, "Bigram " + trigram[1] + " " + trigram[2])
    stats_win.addstr(6, 0, "mean / stdev / median")
    stats_win.hline(8, 0, "-", width-2)
    stats_win.addstr(9, 0, "Trigram " + " ".join(trigram))
    stats_win.addstr(10, 0, "mean / stdev / median")
    
    def message(msg: str, color: int = 0): # mostly for brevity
        gui_util.insert_line_bottom(
            msg, message_win, curses.color_pair(color))
        message_win.refresh()

    def format_stats(data: list):
        try:
            return "{0:^5.1f}   {1:^5.1f}   {2:^5.1f} ms, n={3}".format(
                statistics.mean(data),
                statistics.stdev(data),
                statistics.median(data),
                len(data)
            )
        except statistics.StatisticsError:
            return "Not enough data, n={0}".format(len(data))

    last_time = time.perf_counter_ns()
    next_index = 0
    speeds_01 = []
    speeds_12 = []
    speeds_02 = []
    gui_util.red = 1
    gui_util.green = 2
    gui_util.blue = 3

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

            if key_name != trigram[next_index]:
                if key_name == "esc":
                    message("Finishing test", gui_util.green)
                elif key_name in trigram:
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
        window.refresh()
        window.move(height-1, 0)

    window.refresh()
    curses.flushinp()
    curses.curs_set(1)

    return (speeds_01, speeds_12)