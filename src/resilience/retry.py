import time
import random


def retry_with_backoff(func, max_retries=5, base_delay=1, jitter=True):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            delay = base_delay * (2**attempt)
            if jitter:
                delay *= random.uniform(0.8, 1.2)
            print(
                f"[BACKOFF] Retry {attempt+1}/{max_retries} in {delay:.2f}s due to {e}"
            )
            time.sleep(delay)
    raise RuntimeError("Max retries reached")
