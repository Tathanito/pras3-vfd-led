import time
import math
from pras3 import LEDs, Color

def animate(leds: LEDs, color_list, stop_event=None, speed=0.02):
    """
    Gently pulses the entire 22 LEDs from black to color_list (R,G,B).
    """
    c = Color(*color_list)  # Convert [R,G,B] to a Color object
    num_leds = 22
    step = 0
    while True:
        if stop_event and stop_event.is_set():
            break

        # Sine wave from 0..1
        intensity = (math.sin(step) + 1) / 2.0
        step += 0.1

        # Build 22 LEDs, each tinted by intensity
        data = bytearray()
        r = int(c.r * intensity)
        g = int(c.g * intensity)
        b = int(c.b * intensity)
        for i in range(num_leds):
            data.extend([r, g, b])

        # Remap
        data = leds.remap_pixels(leds.NORMAL_MAPPING, data)
        # Triple up if you do that for your hardware:
        # data = data * 3  # if needed for immediate draw commands
        leds.set_and_draw_pixels(data)

        time.sleep(speed)
