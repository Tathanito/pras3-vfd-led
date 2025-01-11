import time
import math
from pras3 import LEDs

def color_sine_effect(num_leds, step, color1, color2, width, reverse=True):
    """
    Generate an RGB sine wave effect transitioning between color1 and color2.
    """
    half_num_leds = num_leds // 2
    data = bytearray()

    # Generate the first half of the LED data
    for i in range(half_num_leds):
        pos = i + step
        sine_value = (math.sin(pos / width * math.pi) + 1) / 2
        r = int(color1[0] * sine_value + color2[0] * (1 - sine_value))
        g = int(color1[1] * sine_value + color2[1] * (1 - sine_value))
        b = int(color1[2] * sine_value + color2[2] * (1 - sine_value))
        data.extend([r, g, b])

    # Mirror the data
    mirrored_data = bytearray()
    for i in range(half_num_leds - 1, -1, -1):
        mirrored_data.extend(data[i*3:i*3+3])

    if reverse:
        full_data = mirrored_data + data
    else:
        full_data = data + mirrored_data
    return bytes(full_data)

def animate(leds: LEDs, color1, color2, stop_event=None, speed=0.05, width=5, resolution=0.1):
    num_leds = 22
    step = 0.0
    max_step = width * 2
    leds.set_blend_timing(4, 2)

    while True:
        if stop_event and stop_event.is_set():
            break

        pixels = color_sine_effect(num_leds, step, color1, color2, width)
        # Remap to cabinet LED order
        pixels = leds.remap_pixels(leds.NORMAL_MAPPING, pixels)
        leds.fade_to_pixels(pixels)
        time.sleep(speed)
        step += resolution
        if step >= max_step:
            step = 0.0
