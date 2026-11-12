import time
from threading import Lock


class RateLimiter:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self.lock = Lock()
        self.last = 0.0

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last = time.time()
