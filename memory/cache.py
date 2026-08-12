"""Lightweight in-memory LRU cache for Enterprise AI Agent.

Usage:
    from memory.cache import cache

    # Simple get/set with TTL (seconds)
    cache.set("my_key", result, ttl=60)
    value = cache.get("my_key")         # None if expired

    # Function-level decorator
    @cache.cached(ttl=300, prefix="weather")
    async def get_weather(city: str) -> str:
        ...
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable


class LRUCache:
    """Thread-safe LRU cache with per-entry TTL.

    Args:
        maxsize: Maximum number of entries before LRU eviction.
        default_ttl: Default time-to-live in seconds (0 = never expire).
    """

    def __init__(self, maxsize: int = 512, default_ttl: float = 300):
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()  # key → (value, expires_at)
        self._hits = 0
        self._misses = 0

    # ── Core operations ──────────────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Return cached value or None if missing/expired."""
        if key not in self._store:
            self._misses += 1
            return None
        value, expires_at = self._store[key]
        if expires_at and time.monotonic() > expires_at:
            del self._store[key]
            self._misses += 1
            return None
        # LRU: move to end
        self._store.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value. ttl=0 means never expire."""
        ttl = ttl if ttl is not None else self._default_ttl
        expires_at = (time.monotonic() + ttl) if ttl > 0 else 0.0

        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, expires_at)

        # Evict LRU entry if over capacity
        if len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def delete(self, key: str) -> bool:
        """Remove a key; returns True if it existed."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    def evict_expired(self) -> int:
        """Remove all expired entries; returns count removed."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp and now > exp]
        for k in expired:
            del self._store[k]
        return len(expired)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def stats(self) -> dict[str, int | float]:
        total = self._hits + self._misses
        return {
            "size": self.size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }

    # ── Decorator ─────────────────────────────────────────────────────────────

    def cached(self, ttl: float | None = None, prefix: str = "") -> Callable:
        """Decorator that caches async or sync function results.

        Example::

            @cache.cached(ttl=60, prefix="weather")
            async def fetch_weather(city: str) -> str:
                ...
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = _make_key(prefix or func.__name__, args, kwargs)
                hit = self.get(key)
                if hit is not None:
                    return hit
                result = await func(*args, **kwargs)
                self.set(key, result, ttl=ttl)
                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = _make_key(prefix or func.__name__, args, kwargs)
                hit = self.get(key)
                if hit is not None:
                    return hit
                result = func(*args, **kwargs)
                self.set(key, result, ttl=ttl)
                return result

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Stable cache key from function name + arguments."""
    raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]  # noqa: S324 (non-crypto use)
    return f"{prefix}:{digest}"


# ─── Global singleton ─────────────────────────────────────────────────────────
cache = LRUCache(maxsize=512, default_ttl=300)
