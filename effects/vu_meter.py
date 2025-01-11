import pyaudiowpatch as pyaudio
import numpy as np
import time
import threading
from pras3 import LEDs, Color

class AmplitudeContainer:
    def __init__(self):
        self._amp = 0
        self._lock = threading.Lock()

    def set_value(self, val):
        with self._lock:
            self._amp = val

    def get_value(self):
        with self._lock:
            return self._amp

def animate(leds: LEDs, base_color, stop_event=None, scale_factor=1.3):
    """
    Original 'VU meter' approach (linear from 0..active_leds).
    If you want to keep this, you can rename or keep as is.
    ...
    """

    # [same code as your existing animate() function here]
    # Or if you prefer, remove it, and only keep 'animate_symmetric' below.
    pass

def animate_symmetric(leds: LEDs, base_color, stop_event=None, scale_factor=1.3):
    """
    A symmetrical VU meter that fills from center outwards.
    If amplitude is high, it lights from the center to the edges equally.
    This respects the same WASAPI logic, just changes how we fill the 22 LEDs.
    """
    import math

    p = pyaudio.PyAudio()
    amplitude_container = AmplitudeContainer()
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

    if not default_speakers["isLoopbackDevice"]:
        # Attempt to find a loopback version
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break

    def audio_callback(in_data, frame_count, time_info, status):
        data_np = np.frombuffer(in_data, dtype=np.int16)
        magnitude = np.mean(np.abs(data_np)) * scale_factor / 50.0
        if magnitude > 100:
            magnitude = 100
        amplitude_container.set_value(magnitude)
        return (in_data, pyaudio.paContinue)

    stream = p.open(
        format=pyaudio.paInt16,
        channels=default_speakers["maxInputChannels"],
        rate=int(default_speakers["defaultSampleRate"]),
        frames_per_buffer=1024,
        input=True,
        input_device_index=default_speakers["index"],
        stream_callback=audio_callback
    )
    stream.start_stream()

    num_leds = 22
    half = num_leds // 2  # 11
    prev_amp = 0

    def lerp(a, b, t):
        return int(a + (b - a) * t)

    try:
        while True:
            if stop_event and stop_event.is_set():
                break

            amp = amplitude_container.get_value()
            # partial smoothing
            amp = (amp * 0.2) + (prev_amp * 0.8)
            prev_amp = amp

            fraction = amp / 100.0  # 0.0..1.0
            active = int(half * fraction)  # up to 11

            # We'll store brightness for each of the 22 LEDs in an array
            brightness_array = [0.0] * num_leds

            # "Center" is between indices 10 & 11 for an even count of 22
            # We'll fill outward from these two center indices
            center_left = 10
            center_right = 11

            # example: if active=3, we fill indices (10, 11), then (9, 12), then (8, 13)
            for i in range(active):
                brightness = (i+1) / active if active > 0 else 0
                left_index = center_left - i
                right_index = center_right + i

                if left_index >= 0:
                    brightness_array[left_index] = brightness
                if right_index < num_leds:
                    brightness_array[right_index] = brightness

            # Now apply color for each LED
            pixel_data = bytearray(num_leds * 3)
            for i in range(num_leds):
                br = brightness_array[i]  # 0..1
                r = lerp(0, base_color.r, br)
                g = lerp(0, base_color.g, br)
                b = lerp(0, base_color.b, br)
                idx = i * 3
                pixel_data[idx:idx+3] = bytes([r, g, b])

            pixel_data = leds.remap_pixels(leds.NORMAL_MAPPING, pixel_data)
            leds.set_blend_timing(2,1)
            leds.fade_to_pixels(pixel_data)

            time.sleep(0.03)

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
