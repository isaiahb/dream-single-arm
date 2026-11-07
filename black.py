"""A camera with nothing in it: black frames at the configured size and rate, for the right wrist the left-only run lacks."""

import time

import numpy as np


class BlackSource:
    def __init__(self, cfg) -> None:
        self._frame = np.zeros((cfg.height, cfg.width, 3), dtype=np.uint8)
        self._period = 1.0 / cfg.fps
        self._next = time.monotonic()

    def read(self):
        self._next += self._period
        delay = self._next - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            self._next = time.monotonic()
        return True, self._frame.copy()

    def release(self) -> None:
        pass
