from pynput import keyboard
import time
import curses
import queue
import threading

pynput_key_events = queue.Queue()

def on_press(key):
    global pynput_key_events
    pynput_key_events.put((key, "pressed", time.perf_counter_ns()))

def on_release(key):
    global pynput_key_events
    pynput_key_events.put((key, "released", 0))
    if key == keyboard.Key.esc:
        # Stop listener
        return False

def curses_input(window: curses.window, key_events: queue.Queue):
    while True:
        key = window.getkey()
        key_events.put((key, "pressed", time.perf_counter_ns()))
        if key == "^[":
            break

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
            submit_line("Key {2} pressed after {0:.1f} ms ({1} wpm)".format(ms, int(wpm), key_name), window)
            last_time = new_time
        # else:
        #     message('{0} released'.format(key), window)
        key_events.task_done()
    window.refresh()
    return last_time

def submit_line(str, window: curses.window):
    window.move(0,0)
    window.deleteln()
    ymax, xmax = window.getmaxyx()
    window.addnstr(ymax-1, 0, str, xmax-1)

def test(stdscr: curses.window):
    curses.curs_set(0)
    height, width = stdscr.getmaxyx()
    subwin_height = 3
    pynput_win = stdscr.subwin(height - subwin_height - 1, int(width/2), subwin_height, 0)
    curses_win = stdscr.subwin(height - subwin_height - 1, int(width/2), subwin_height, int(width/2))

    pynput_last_time = time.perf_counter_ns()
    curses_last_time = pynput_last_time

    # Collect events until released
    pynput_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    pynput_listener.start()
    pynput_listener.wait()
    global pynput_key_events
    curses_key_events = queue.Queue()
    curses_input_thread = threading.Thread(target=curses_input, args=(curses_win,curses_key_events), daemon=True)
    curses_input_thread.start()
    while pynput_listener.running:
        time.sleep(0.01)
        pynput_last_time = check_queue(pynput_win, pynput_key_events, pynput_last_time)
        curses_last_time = check_queue(curses_win, curses_key_events, curses_last_time)
        stdscr.move(height-1, 0)
    stdscr.getch()
    curses.curs_set(1)