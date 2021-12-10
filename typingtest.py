from pynput import keyboard
import time
import curses
import queue
import layout
import gui_util

key_events = queue.Queue()

def on_press(key):
    global key_events
    key_events.put((key, "pressed", time.perf_counter_ns()))

def on_release(key):
    global key_events
    key_events.put((key, "released", 0))
    if key == keyboard.Key.esc:
        # Stop listener
        return False

def check_queue(window: curses.window, key_events: queue.Queue, last_time):
    while not key_events.empty():
        key, press, new_time = key_events.get()        
        if press == "pressed":
            try:
                key_name = key.char
            except AttributeError:
                key_name = key
            ms = (new_time - last_time)/1e6
            wpm = 12000/ms
            gui_util.insert_line_bottom("Key {2} pressed after {0:.1f} ms ({1} wpm)".format(ms, int(wpm), key_name), window)
            last_time = new_time
        # else:
        #     message('{0} released'.format(key), window)
        key_events.task_done()
    window.refresh()
    return last_time

def test(window: curses.window, trigram, active_layout: layout.Layout):
    '''Run a typing test with the specified trigram.

    trigram is either a 3-char string, or a list of three key names.'''

    curses.echo(False)
    if isinstance(trigram, str):
        trigram = [char for char in trigram]
    window.clear()
    window.addstr(0, 0, "Typing test - Press esc to finish")
    window.addstr(1, 0, "Active layout: " + active_layout.name)
    window.addstr(2, 0, "Trigram: " + " ".join(trigram))
    window.refresh()
    curses.curs_set(0)
    height, width = window.getmaxyx()
    typing_test_win = window.derwin(height - 4, width, 3, 0)

    last_time = time.perf_counter_ns()

    # Collect events until released
    pynput_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    pynput_listener.start()
    pynput_listener.wait()
    global key_events
    while pynput_listener.running:
        time.sleep(0.01)
        last_time = check_queue(typing_test_win, key_events, last_time)
        window.move(height-1, 0)

    window.erase()
    curses.flushinp()
    curses.curs_set(1)