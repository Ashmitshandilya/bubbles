"""Small in-process caches with a time limit, shared-miss protection and stats for the admin portal.

Rules (health data): every cache here is either user-scoped (the key includes the user) or holds no user data, values are never
written to disk, and a failure inside the cache falls back to the normal computation. Errors are never cached.
"""
# ponytail: process memory only (one Render instance); a Redis-backed class with the same methods is the upgrade path.
from __future__ import annotations

import threading
import time
from typing import Any, Callable

_registry: dict[str, "TTLCache"] = {}
WAIT_LIMIT_S = 30.0


class _Flight:
    """One computation in progress; callers asking for the same key wait for it instead of running it again."""

    def __init__(self) -> None:
        self.done = threading.Event()
        self.value: Any = None
        self.error: BaseException | None = None


class TTLCache:
    def __init__(self, name: str, ttl_s: float, max_entries: int = 1000, clock: Callable[[], float] = time.monotonic):
        self.name, self.ttl_s, self.max_entries, self._clock = name, ttl_s, max_entries, clock
        self.enabled = True
        self._data: dict[Any, tuple[float, Any]] = {}
        self._inflight: dict[Any, _Flight] = {}
        self._lock = threading.Lock()
        self.hits = self.misses = self.shared = self.invalidations = self.errors = 0
        self._miss_ms = 0.0
        _registry[name] = self

    def get_or_compute(self, key: Any, compute: Callable[[], Any], ttl_for: Callable[[Any], float] | None = None) -> Any:
        """The cached value, or ``compute()`` stored for ``ttl_s`` (or ``min(ttl_s, ttl_for(value))``; 0 or less = not stored)."""
        if not self.enabled:
            return compute()
        try:
            with self._lock:
                hit = self._data.get(key)
                if hit is not None and hit[0] > self._clock():
                    self.hits += 1
                    return hit[1]
                flight = self._inflight.get(key)
                leader = flight is None
                if leader:
                    flight = self._inflight[key] = _Flight()
                    self.misses += 1
                else:
                    self.shared += 1
        except Exception:  # noqa: BLE001 - a broken cache must never break the request
            self.errors += 1
            return compute()
        if not leader:
            if not flight.done.wait(WAIT_LIMIT_S):   # the first caller is stuck: do the work ourselves rather than wait forever
                return compute()
            if flight.error is not None:
                raise flight.error
            return flight.value
        started = time.perf_counter()
        try:
            flight.value = compute()
            return flight.value
        except BaseException as error:
            flight.error = error
            raise
        finally:
            try:
                with self._lock:
                    self._miss_ms += (time.perf_counter() - started) * 1000
                    if self._inflight.get(key) is flight:  # not invalidated while it ran
                        try:
                            ttl = self.ttl_s if flight.error is not None or ttl_for is None else min(self.ttl_s, ttl_for(flight.value))
                        except Exception:  # noqa: BLE001 - an unreadable lifetime means "do not store"
                            ttl = 0
                        if flight.error is None and ttl > 0:
                            self._data[key] = (self._clock() + ttl, flight.value)
                            self._evict()
                        del self._inflight[key]
            finally:
                flight.done.set()   # whatever happened above, nobody keeps waiting

    def _evict(self) -> None:
        if len(self._data) <= self.max_entries:
            return
        now = self._clock()
        for k in [k for k, (exp, _) in self._data.items() if exp <= now]:
            self._data.pop(k, None)
        while len(self._data) > self.max_entries:
            self._data.pop(next(iter(self._data)))

    def peek(self, key: Any) -> Any:
        """The cached value, or None (counted as a hit or a miss). For "remember that X is done" flags."""
        if not self.enabled:
            return None
        with self._lock:
            hit = self._data.get(key)
            if hit is not None and hit[0] > self._clock():
                self.hits += 1
                return hit[1]
            self.misses += 1
            return None

    def put(self, key: Any, value: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._data[key] = (self._clock() + self.ttl_s, value)
            self._evict()

    def invalidate(self, key: Any) -> None:
        with self._lock:
            if self._data.pop(key, None) is not None:
                self.invalidations += 1
            self._inflight.pop(key, None)  # a computation already running may not store a value read before the change

    def clear(self) -> None:
        with self._lock:
            self.invalidations += len(self._data)
            self._data.clear()
            self._inflight.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            lookups = self.hits + self.misses + self.shared
            avg_miss = self._miss_ms / self.misses if self.misses else 0.0
            return {
                "name": self.name, "enabled": self.enabled, "ttl_s": self.ttl_s, "entries": len(self._data),
                "hits": self.hits, "misses": self.misses, "shared": self.shared, "invalidations": self.invalidations,
                "errors": self.errors, "hit_rate": round((self.hits + self.shared) / lookups, 3) if lookups else None,
                "avg_miss_ms": round(avg_miss, 1), "saved_ms_estimate": round((self.hits + self.shared) * avg_miss),
            }


def all_stats() -> list[dict[str, Any]]:
    return [cache.stats() for cache in _registry.values()]


def get(name: str) -> TTLCache | None:
    return _registry.get(name)


def clear_all() -> int:
    for cache in _registry.values():
        cache.clear()
    return len(_registry)
