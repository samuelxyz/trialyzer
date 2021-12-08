from pynput import keyboard
import time

def on_press(key):
    global last_time
    new_time = time.perf_counter()
    try:
        print('alphanumeric key {0} pressed'.format(
            key.char))
    except AttributeError:
        print('special key {0} pressed'.format(
            key))
    ms = (new_time - last_time)*1000
    wpm = 12000/ms
    print("Time between keystrokes was {0} ms ({1} wpm)".format(ms, wpm))
    last_time = new_time

def on_release(key):
    print('{0} released'.format(
        key))
    if key == keyboard.Key.esc:
        # Stop listener
        return False


print("Press 'esc' to exit")

last_time = time.perf_counter()

# Collect events until released
with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
    listener.join()

# ...or, in a non-blocking fashion:
# listener = keyboard.Listener(
#     on_press=on_press,
#     on_release=on_release)
# listener.start()

