"""The shared server cache: time limit, user isolation by key, shared misses, invalidation, failure fallback and stats."""
import threading
import time

import pytest

from ttl_cache import TTLCache, all_stats, clear_all


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_hit_until_the_time_limit_then_recompute():
    clock, calls = Clock(), []
    cache = TTLCache("t-ttl", ttl_s=10, clock=clock)
    compute = lambda: calls.append(1) or len(calls)  # noqa: E731
    assert cache.get_or_compute("k", compute) == 1
    assert cache.get_or_compute("k", compute) == 1
    clock.t = 11
    assert cache.get_or_compute("k", compute) == 2
    s = cache.stats()
    assert (s["hits"], s["misses"]) == (1, 2)


def test_keys_never_cross_users():
    cache = TTLCache("t-users", ttl_s=60)
    assert cache.get_or_compute(("user-a", "consent"), lambda: True) is True
    assert cache.get_or_compute(("user-b", "consent"), lambda: False) is False
    assert cache.get_or_compute(("user-a", "consent"), lambda: False) is True


def test_errors_are_not_cached_and_reach_the_caller():
    cache = TTLCache("t-errors", ttl_s=60)

    def boom():
        raise RuntimeError("db down")

    with pytest.raises(RuntimeError):
        cache.get_or_compute("k", boom)
    assert cache.get_or_compute("k", lambda: "ok") == "ok"


def test_concurrent_identical_misses_share_one_computation():
    cache = TTLCache("t-flight", ttl_s=60)
    calls, gate = [], threading.Event()

    def slow():
        calls.append(1)
        gate.wait(2)
        return "value"

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get_or_compute("k", slow))) for _ in range(5)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    gate.set()
    for t in threads:
        t.join(3)
    assert results == ["value"] * 5
    assert len(calls) == 1
    assert cache.stats()["shared"] == 4


def test_invalidate_drops_the_value_and_a_running_computation_cannot_store_a_stale_one():
    cache = TTLCache("t-inval", ttl_s=60)
    cache.get_or_compute("k", lambda: "old")
    cache.invalidate("k")
    assert cache.get_or_compute("k", lambda: "new") == "new"

    def compute_then_invalidated():
        cache.invalidate("k2")   # the user changed the value while it was being read
        return "stale"

    assert cache.get_or_compute("k2", compute_then_invalidated) == "stale"
    assert cache.get_or_compute("k2", lambda: "fresh") == "fresh"


def test_a_disabled_cache_always_computes():
    cache = TTLCache("t-off", ttl_s=60)
    cache.enabled = False
    calls = []
    for _ in range(3):
        cache.get_or_compute("k", lambda: calls.append(1))
    assert len(calls) == 3


def test_size_is_bounded():
    cache = TTLCache("t-size", ttl_s=60, max_entries=3)
    for i in range(10):
        cache.get_or_compute(i, lambda i=i: i)
    assert cache.stats()["entries"] == 3


def test_a_broken_cache_falls_back_to_the_computation(monkeypatch):
    cache = TTLCache("t-broken", ttl_s=60)
    monkeypatch.setattr(cache, "_data", None)   # any internal failure
    assert cache.get_or_compute("k", lambda: 42) == 42
    assert cache.errors == 1


def test_registry_reports_and_clears_every_cache():
    cache = TTLCache("t-registry", ttl_s=60)
    cache.get_or_compute("k", lambda: 1)
    assert any(s["name"] == "t-registry" for s in all_stats())
    clear_all()
    assert cache.stats()["entries"] == 0


def test_a_waiter_never_waits_forever_on_a_stuck_first_caller(monkeypatch):
    import ttl_cache
    monkeypatch.setattr(ttl_cache, "WAIT_LIMIT_S", 0.2)
    cache = TTLCache("t-stuck", ttl_s=60)
    release = threading.Event()
    threading.Thread(target=lambda: cache.get_or_compute("k", lambda: release.wait(3) or "late"), daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    assert cache.get_or_compute("k", lambda: "own") == "own"
    assert time.monotonic() - started < 1.5
    release.set()
