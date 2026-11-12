import pytest
import time
from concurrent.futures import ThreadPoolExecutor

from MonaaLisa.src.SemanticPaper.api.rate_limiter import RateLimiter


@pytest.fixture
def rate_limiter():
    """Creates a RateLimiter instance with a 0.1 second interval for fast tests."""
    return RateLimiter(min_interval=0.1)


class TestWait:
    """Tests the core timing logic in wait()."""

    def test_first_call_does_not_wait(self, rate_limiter):
        """
        Tests: if elapsed < self.min_interval: time.sleep(...)

        First call should pass immediately since self.last starts at 0.0,
        meaning elapsed time is always greater than min_interval.
        """
        start = time.time()
        rate_limiter.wait()
        elapsed = time.time() - start

        # First call should be nearly instant (< 50ms tolerance)
        assert elapsed < 0.05

    def test_enforces_minimum_interval_between_calls(self, rate_limiter):
        """
        Tests: if elapsed < self.min_interval: time.sleep(self.min_interval - elapsed)

        Immediate second call must wait for the remaining interval.
        Without this check, API rate limits would be violated.
        """
        rate_limiter.wait()  # First call, sets self.last

        start = time.time()
        rate_limiter.wait()  # Second call, should wait
        elapsed = time.time() - start

        # Should have waited approximately min_interval (0.1s), with tolerance
        assert elapsed >= 0.09  # Allow small timing variance

    def test_no_wait_when_interval_exceeded(self, rate_limiter):
        """
        Tests: if elapsed < self.min_interval (False branch)

        When enough time has passed, wait() should return immediately.
        """
        rate_limiter.wait()
        time.sleep(0.15)  # Wait longer than min_interval

        start = time.time()
        rate_limiter.wait()
        elapsed = time.time() - start

        # Should pass immediately since interval already exceeded
        assert elapsed < 0.05

    def test_updates_last_timestamp_after_wait(self, rate_limiter):
        """
        Tests: self.last = time.time()

        The timestamp must be updated AFTER sleeping, not before.
        If updated before, subsequent calls would not wait correctly.
        """
        rate_limiter.wait()
        first_last = rate_limiter.last

        time.sleep(0.05)
        rate_limiter.wait()  # This should wait ~0.05s more
        second_last = rate_limiter.last

        # second_last should be at least min_interval after first_last
        assert second_last >= first_last + rate_limiter.min_interval - 0.01


class TestThreadSafety:
    """Tests that the Lock correctly serializes concurrent access."""

    def test_concurrent_calls_respect_interval(self):
        """
        Tests: with self.lock: ...

        Multiple threads calling wait() simultaneously must each wait
        for min_interval relative to the previous call.
        Without the lock, calls could overlap and violate rate limits.
        """
        limiter = RateLimiter(min_interval=0.1)
        timestamps = []

        def record_call():
            limiter.wait()
            timestamps.append(time.time())

        # Launch 3 threads simultaneously
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(record_call) for _ in range(3)]
            for f in futures:
                f.result()

        # Sort timestamps and check intervals
        timestamps.sort()
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i - 1]
            # Each call should be at least min_interval apart (with tolerance)
            assert interval >= 0.09, f"Interval {i}: {interval}s is too short"

    def test_lock_prevents_race_conditions(self):
        """
        Tests: with self.lock: ... (atomic read-modify-write)

        Without the lock, concurrent reads of self.last could both see
        the old value, causing both threads to skip waiting.
        """
        limiter = RateLimiter(min_interval=0.1)
        call_times = []

        def timed_call():
            start = time.time()
            limiter.wait()
            call_times.append(time.time() - start)

        # Launch 5 threads as fast as possible
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(timed_call) for _ in range(5)]
            for f in futures:
                f.result()

        # Total time should be at least (n-1) * min_interval
        # because calls are serialized
        total_wait = sum(call_times)
        # At least 4 calls had to wait (first one doesn't)
        assert total_wait >= 0.35  # ~4 * 0.1s with some tolerance

