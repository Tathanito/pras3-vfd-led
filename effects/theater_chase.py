import time
from pras3 import LEDs

def animate(leds: LEDs, color_list, stop_event=None, speed=0.05):
    """
    Theater chase effect: dotted lights moving across the 22 LEDs.
    """
    num_leds = 22
    c_r, c_g, c_b = color_list

    offset = 0
    while True:
        if stop_event and stop_event.is_set():
            break

        data = bytearray()
        for i in range(num_leds):
            # This pattern lights up every 3rd LED, you can vary it
            if (i + offset) % 3 == 0:
                data.extend([c_r, c_g, c_b])
            else:
                data.extend([0, 0, 0])

        # Remap
        data = leds.remap_pixels(leds.NORMAL_MAPPING, data)
        leds.set_and_draw_pixels(data)

        offset = (offset + 1) % 3
        time.sleep(speed)
