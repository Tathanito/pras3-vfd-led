import psutil
import time
import random
import sys
import os
import logging
from threading import Thread, Event, Lock

###############################################################################
# CONFIG: Debug mode toggle
###############################################################################
DEBUG_MODE = True  # If False => logs only WARNING/ERROR. If True => logs INFO/DEBUG.

if DEBUG_MODE:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

###############################################################################
# Local Imports
###############################################################################
from pras3 import LEDs, VFD, Color
from effects import rainbow, vu_meter, color_sine
from gameconfig import games_config, possible_effects

###############################################################################
# Global Variables
###############################################################################
watchdog_poll_rate = 5  # seconds
current_game_exe = 'NO_GAME'

led_thread = None
stop_event = Event()
led_lock = Lock()

leds = LEDs()
vfd = VFD()

coin_thread = None
coin_stop_event = Event()

unknown_games_file = os.path.join(os.path.expanduser("~"), "unknown_games.txt")

CASA_SPACING = "           Casa de Tathan           "

###############################################################################
# Coin blink logic
###############################################################################
def blink_once(blink_color=(255, 255, 255), duration=0.3):
    """Briefly override LEDs with blink_color, then let effect resume."""
    def do_blink():
        try:
            with led_lock:
                # 22 LEDs => 66 bytes => possibly replicate *3 if needed
                temp = bytearray()
                for _ in range(22):
                    temp.extend(blink_color)
                big = temp * 3
                leds.set_and_draw_pixels(big)
            time.sleep(duration)
            # effect will overwrite
        except Exception as e:
            logging.error(f"Error in blink_once: {e}")

    Thread(target=do_blink, daemon=True).start()


def check_coin():
    """Placeholder coin detection."""
    return False

def coin_watcher():
    while not coin_stop_event.is_set():
        time.sleep(0.2)
        if check_coin():
            # blink in bright yellow
            blink_once((255, 255, 0), 0.3)


###############################################################################
# LED effect with built-in hardware fade
###############################################################################
def run_led_effect(effect_name, led_color, led_color_2):
    """
    Stop old effect, set blend timing, do fade_to_pixels to an initial pattern,
    then start the infinite effect if needed (rainbow, etc.).
    """
    global led_thread

    if led_thread and led_thread.is_alive():
        stop_event.set()
        led_thread.join()
        stop_event.clear()

    with led_lock:
        # set a more gentle fade
        # e.g. 60 frames, 2 ms each => 120ms total, you can adjust to preference
        leds.set_blend_timing(60, 2)

        # Build initial buffer for the new effect
        if effect_name == 'solid':
            c = Color(*led_color)
            init_px = leds.build_pixels(c, c, c)  # 66 bytes
            big_buf = init_px * 3
            leds.fade_to_pixels(big_buf)

        elif effect_name == 'two color':
            # just fade into color1
            c = Color(*led_color)
            init_px = leds.build_pixels(c, c, c)
            big_buf = init_px * 3
            leds.fade_to_pixels(big_buf)

        elif effect_name == 'vu meter':
            c = Color(*led_color)
            init_px = leds.build_pixels(c, c, c)
            big_buf = init_px * 3
            leds.fade_to_pixels(big_buf)

        elif effect_name == 'rainbow':
            # Instead of gray or white, let's build an actual initial rainbow frame
            # We'll define a function that returns a single rainbow frame
            # that you'd do in the main effect:
            first_frame = build_rainbow_frame(22, step=0)
            big_buf = first_frame * 3
            leds.fade_to_pixels(big_buf)

        else:
            # fallback => color1
            c = Color(*led_color)
            init_px = leds.build_pixels(c, c, c)
            big_buf = init_px * 3
            leds.fade_to_pixels(big_buf)

    # wait for fade to finish
    time.sleep(0.5)

    def effect_runner():
        try:
            if effect_name == 'solid':
                while not stop_event.is_set():
                    time.sleep(0.25)
            elif effect_name == 'two color':
                color_sine.animate(leds, led_color, led_color_2, stop_event=stop_event)
            elif effect_name == 'rainbow':
                # start the actual rainbow loop
                rainbow.animate(leds, speed=0.01, stop_event=stop_event)
            elif effect_name == 'vu meter':
                c_obj = Color(*led_color)
                vu_meter.animate_symmetric(leds, c_obj, stop_event=stop_event)
            else:
                while not stop_event.is_set():
                    time.sleep(0.25)
        except Exception as e:
            logging.error(f"Error in effect_runner: {e}")

    led_thread = Thread(target=effect_runner, daemon=True)
    led_thread.start()

def build_rainbow_frame(num_leds, step=0):
    """
    Build a single "rainbow" frame (22 * 3 bytes) so we can fade into it initially.
    """
    from math import floor
    # from rainbow code: we do something like:
    data = bytearray()
    for i in range(num_leds):
        pixel_index = (i * 256 // num_leds + step) & 255
        r, g, b = wheel(pixel_index)
        data.extend([r, g, b])
    # Then re-map to NORMAL_MAPPING or not (depends on your code).
    data = leds.remap_pixels(leds.NORMAL_MAPPING, data)
    return data

def wheel(pos):
    """Helper for rainbow color generation."""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

###############################################################################
# VFD
###############################################################################
def set_vfd_image(path):
    try:
        vfd.turn_on(True)
        with open(path, "r", encoding='utf-8') as f:
            lines = f.readlines()
        if lines and lines[-1].strip() == "":
            lines.pop()
        w, h, image = vfd.convert_ascii_art(lines)
        image = vfd.rotate_bitmap(image, w, h)
        vfd.draw_bitmap(0, 0, w, h // 8, image)
    except Exception as e:
        logging.error(f"Error in set_vfd_image: {e}")

def set_vfd_text(text):
    """
    If blank => show CASA_SPACING. Else => text + CASA_SPACING.
    Write it twice with a short sleep to ensure it's displayed.
    """
    try:
        if not text.strip():
            final_text = CASA_SPACING
        else:
            final_text = f"{text}   {CASA_SPACING}"

        vfd.set_text_window(0, 2, 160)
        vfd.set_text_scroll_speed(1)
        vfd.set_brightness(4)

        vfd.write_scroll_text(final_text)
        time.sleep(0.3)
        vfd.write_scroll_text(final_text)

        logging.info(f"VFD text => '{text}' => '{final_text}'")

    except Exception as e:
        logging.error(f"Error in set_vfd_text: {e}")

def write_unknown_game(game_exe):
    try:
        if not os.path.exists(unknown_games_file):
            with open(unknown_games_file, "w") as f:
                f.write("# Unknown Games\n\n")

        with open(unknown_games_file, "a") as f:
            f.write(
                f"'{game_exe}': {{\n"
                f"    'launch_path': r'C:\\Games\\Unknown\\{game_exe}',\n"
                f"    'scroll_text': 'Playing Unknown Game ({game_exe})',\n"
                f"}},\n\n"
            )
    except Exception as e:
        logging.error(f"Error in write_unknown_game: {e}")


###############################################################################
# apply_game_settings
###############################################################################
def apply_game_settings(game_exe):
    """
    If it's NO_GAME => forcibly set text to blank => we show CASA_SPACING,
    led_color => [255,255,0], effect => 'solid', etc.
    Otherwise, read from gameconfig or do unknown fallback.
    """
    try:
        # reset the VFD
        vfd.reset()
        vfd.turn_on(True)

        if game_exe == 'NO_GAME':


            # Force the color to [255,255,0] (yellow)
            # Force the text to blank so set_vfd_text => CASA_SPACING
#            set_vfd_text('                      {CASA_SPACING}                      ')
#            time.sleep(1.0)
#            txt = cfg.get('scroll_text', '')
#            ascii_file = cfg.get('ascii_file', None)
#
#            if ascii_file:
#                set_vfd_image(ascii_file)

#            set_vfd_text(txt)
#            time.sleep(1.0)

#            eff = cfg.get('led_effect', 'solid')
#            c1 = cfg.get('led_color', [255, 255, 255])
#            c2 = cfg.get('led_color_2', [0, 0, 0])
#            txt = cfg.get('scroll_text', 'CASA DE TATHAN')

            if ascii_file:
                set_vfd_image(ascii_file)

            set_vfd_text(txt)
            time.sleep(1.0)



            # run_led_effect => 'solid'
            c1 = [215,230,0]
            logging.info("Applying NO_GAME => solid yellow + Casa de Tathan text")
            run_led_effect('solid', c1, [0,0,0])
            return

        # Else, check known config
        cfg = games_config.get(game_exe)
        if cfg:
            eff = cfg.get('led_effect', 'solid')
            c1 = cfg.get('led_color', [255, 255, 255])
            c2 = cfg.get('led_color_2', [0, 0, 0])
            txt = cfg.get('scroll_text', '')
            ascii_file = cfg.get('ascii_file', None)

            if ascii_file:
                set_vfd_image(ascii_file)

            set_vfd_text(txt)
            time.sleep(1.0)

            # If effect == 'solid', maybe turn off scroll
#            if eff == 'solid':
#                vfd.set_text_scroll(False)

            logging.info(f"Starting effect => {eff}, c1={c1}, c2={c2}")
            run_led_effect(eff, c1, c2)

        else:
            # unknown game
            logging.warning(f"Unknown game: {game_exe}")
            write_unknown_game(game_exe)

            c1 = random_color()
            c2 = random_color()
            eff = random.choice(possible_effects)
            txt = f"Playing Unknown Game ({game_exe})"

            set_vfd_text(txt)
            time.sleep(1.0)
            run_led_effect(eff, c1, c2)

    except Exception as e:
        logging.error(f"Error in apply_game_settings: {e}")


###############################################################################
# find_game_exe_in_target_folders
###############################################################################
def find_game_exe_in_target_folders():
    """
    Look for a process whose exe path starts with c:\\games or c:\\emulators.
    Return .name if found, else None.
    """
    try:
        targets = [r"c:\games", r"c:\emulators"]
        for proc in psutil.process_iter(['pid','name','exe']):
            try:
                pexe = proc.info['exe']
                if not pexe:
                    continue
                pexe_lower = pexe.lower()
                for t in targets:
                    if pexe_lower.startswith(t.lower()):
                        logging.info(f"Found game: {proc.info['name']} => {pexe}")
                        return proc.info['name']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logging.error(f"Error in find_game_exe_in_target_folders: {e}")
    return None


###############################################################################
# Main
###############################################################################
if __name__ == "__main__":
    try:
        logging.info(f"Game detection started, checking every {watchdog_poll_rate} secs.")

        # Start coin watcher
        coin_thread = Thread(target=coin_watcher, daemon=True)
        coin_thread.start()

        # Start with NO_GAME
        apply_game_settings('NO_GAME')
        current_game_exe = 'NO_GAME'

        while True:
            new_game_exe = find_game_exe_in_target_folders()
            logging.info(f"Detected game exe: {new_game_exe}")

            if new_game_exe:
                if new_game_exe != current_game_exe:
                    logging.info(f"Switching from '{current_game_exe}' to '{new_game_exe}'")
                    apply_game_settings(new_game_exe)
                    current_game_exe = new_game_exe
                else:
                    logging.info(f"{new_game_exe} is already active. No action.")
            else:
                if current_game_exe != 'NO_GAME':
                    logging.info("No recognized game => applying NO_GAME.")
                    apply_game_settings('NO_GAME')
                    current_game_exe = 'NO_GAME'
                else:
                    logging.info("Still NO_GAME => no action.")

            time.sleep(watchdog_poll_rate)

    except KeyboardInterrupt:
        logging.info("Exiting on Ctrl+C")
        coin_stop_event.set()
    except Exception as exc:
        logging.error(f"ERROR: {exc}")
        coin_stop_event.set()
        sys.exit(1)
