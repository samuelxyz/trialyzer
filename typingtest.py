from pynput import keyboard
import time
import curses
import queue

last_time = time.perf_counter_ns()

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

def check_queue(window: curses.window):
    global key_events
    while not key_events.empty():
        key, press, new_time = key_events.get()        
        if press == "pressed":
            global last_time
            try:
                key_name = key.char
            except AttributeError:
                key_name = key
            ms = (new_time - last_time)/1e6
            wpm = 12000/ms
            submit_line("Key {2} pressed after {0:.1f} ms ({1} wpm)".format(ms, int(wpm), key_name), window)
            last_time = new_time
        else:
            # message('{0} released'.format(key), window)
            pass
        key_events.task_done()
    window.refresh()

def submit_line(str, window: curses.window):
    window.move(0,0)
    window.deleteln()
    ymax, xmax = window.getmaxyx()
    window.addstr(ymax-1, 0, str)

def test(stdscr: curses.window):
    curses.curs_set(0)
    height, width = stdscr.getmaxyx()
    subwin_height = 3
    message_win = stdscr.subwin(height - subwin_height - 1, width, subwin_height, 0)

    # Collect events until released
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    listener.wait()
    while listener.running:
        time.sleep(0.01)
        check_queue(message_win)
    stdscr.move(height-1, 0)
    curses.curs_set(1)