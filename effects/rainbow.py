import time
from pras3 import LEDs

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def rainbow(num_leds, step):
    """
    Generate a rainbow gradient across num_leds, offset by step.
    Returns exactly (num_leds*3) bytes.
    """
    data = bytearray()
    for i in range(num_leds):
        pixel_index = (i * 256 // num_leds + step) & 255
        r, g, b = wheel(pixel_index)
        data.extend([r, g, b])
    return data

def animate(leds: LEDs, speed=0.01, stop_event=None):
    num_leds = 22
    step = 0

    while True:
        if stop_event and stop_event.is_set():
            break

        # Build the 22-LED rainbow, etc...
        ...

        pixels_22 = rainbow(num_leds, step)

        # Remap to the P-RAS3 order (still 22 LEDs, 66 bytes)
        pixels_22 = leds.remap_pixels(leds.NORMAL_MAPPING, pixels_22)

        # *** Replicate the array 3× to match the hardware’s 198-byte format
        big_pixels_66 = pixels_22 * 3  # 66 bytes * 3 = 198 bytes total

        # Update the hardware instantly
        leds.set_and_draw_pixels(big_pixels_66)

        step = (step + 1) % 256
        time.sleep(speed)
