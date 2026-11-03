"""Bounded network workers and process-local scheduling controls."""
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from urllib.parse import urlsplit

# All scraper writes, including direct audits, share this lock on SQLite.
# This is intentionally process-local; deployment still uses one app process.
SCRAPER_WRITE_LOCK = threading.RLock()
_host_lock = threading.Lock()
_hosts = {}
_provider_next = {}
_provider_slots = {'duckduckgo': threading.BoundedSemaphore(4),
                   'nominatim': threading.BoundedSemaphore(4),
                   'bing': threading.BoundedSemaphore(8),
                   'photon': threading.BoundedSemaphore(8)}
_provider_clocks = {provider: threading.Lock() for provider in _provider_slots}


def worker_count(variable, default, maximum):
    try:
        value = int(os.environ.get(variable, str(default)))
    except ValueError:
        return default
    return min(max(value, 1), maximum)


def parallel_results(function, items, workers):
    """Yield completions with at most `workers` submitted tasks, including failures.

    Explicitly close the iterator on early exit to cancel queued work. In-flight
    requests finish under their existing timeouts before executor shutdown.
    """
    iterator = iter(items)
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='devlead-scrape')
    pending = {}
    try:
        def submit_one():
            try:
                item = next(iterator)
            except StopIteration:
                return False
            pending[pool.submit(function, item)] = item
            return True

        for _ in range(workers):
            if not submit_one():
                break
        while pending:
            ready, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in ready:
                item = pending.pop(future)
                try:
                    result, error = future.result(), None
                except Exception as exc:
                    result, error = None, exc
                yield item, result, error
            # Refill only after the consumer has handled the current completions.
            while len(pending) < workers and submit_one():
                pass
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)


@contextmanager
def website_slot(url):
    """One in-flight website request per hostname across both active batches."""
    host = (urlsplit(url).hostname or '').lower().removeprefix('www.')
    with _host_lock:
        state = _hosts.setdefault(host, {'semaphore': threading.BoundedSemaphore(1), 'users': 0})
        state['users'] += 1
    try:
        with state['semaphore']:
            yield
    finally:
        with _host_lock:
            state['users'] -= 1
            if not state['users']:
                del _hosts[host]


@contextmanager
def discovery_slot(provider, fast_mode=False):
    """Controls request spacing per provider with fast scrap support."""
    slot = _provider_slots.get(provider)
    clock = _provider_clocks.get(provider)
    if not slot or not clock:
        yield
        return

    min_delay = 0.05 if fast_mode else 0.8
    with slot:
        with clock:
            now = time.monotonic()
            delay = _provider_next.get(provider, now) - now
            if delay > 0 and not fast_mode:
                time.sleep(min(delay, 1.0))
            _provider_next[provider] = time.monotonic() + min_delay
        yield

