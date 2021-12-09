from pynput import keyboard
import time
import curses
import queue

def on_press(key):
    global key_events
    key_events.put((key, "pressed", time.perf_counter()))

def on_release(key):
    global key_events
    key_events.put((key, "released", 0))
    if key == keyboard.Key.esc:
        # Stop listener
        return False

last_time = time.perf_counter()
first_row = 3
num_rows = 5
row_limit = first_row + num_rows
past_messages = []

key_events = queue.Queue()

def check_queue(stdscr):
    global key_events
    try:
        key, press, new_time = key_events.get()
    except queue.Empty:
        return
        
    if press == "pressed":
        global last_time
        try:
            key_name = key.char
        except AttributeError:
            key_name = key
        ms = (new_time - last_time)*1000
        wpm = 12000/ms
        message("Key {2} pressed after {0} ms ({1} wpm)".format(ms, wpm, key_name), stdscr)
        last_time = new_time
    else:
        message('{0} released'.format(key), stdscr)

def message(str, stdscr):
    global past_messages
    past_messages.append(str)
    global num_rows
    if len(past_messages) > num_rows:
        past_messages.pop(0)
    
    global first_row
    global row_limit
    for i in range(len(past_messages)):
        stdscr.addstr(first_row + i, 0, past_messages[i] + " "*70)
    stdscr.refresh()

def test(stdscr):
    global window
    stdscr = stdscr   

    # Collect events until released
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    listener.wait()
    while listener.running:
        time.sleep(0.05)
        check_queue(stdscr)

# ...or, in a non-blocking fashion:
# listener = keyboard.Listener(
#     on_press=on_press,
#     on_release=on_release)
# listener.start()

