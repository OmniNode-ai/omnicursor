"""Publisher protocol and NoopPublisher (stdlib only).

Publisher is a typing.Protocol so any object with a publish() method is
accepted without inheriting from a base class.  NoopPublisher logs each
event at INFO level and records it in self.events for test inspection.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Protocol, Tuple


class PublishCounter:
    """Thread-safe count of successful publisher.publish() calls (returns True)."""

    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def record(self, n: int = 1) -> None:
        with self._lock:
            self._value += n

    def value(self) -> int:
        with self._lock:
            return self._value


class CountingPublisher:
    """Delegates to an inner publisher and increments *counter* on success."""

    def __init__(self, inner: Publisher, counter: PublishCounter) -> None:
        self._inner = inner
        self._counter = counter

    def publish(self, event_type: str, payload: Dict) -> bool:
        ok = self._inner.publish(event_type, payload)
        if ok:
            self._counter.record()
        return ok

    def flush(self, *args, **kwargs):
        flush = getattr(self._inner, "flush", None)
        if flush is not None:
            return flush(*args, **kwargs)
        return None


class Publisher(Protocol):
    def publish(self, event_type: str, payload: Dict) -> bool:
        """Publish one event.  Returns True on success, False on failure."""
        ...


class NoopPublisher:
    """Publisher that records events in memory and always returns True."""

    def __init__(self, *, log: logging.Logger | None = None) -> None:
        self._log = log or logging.getLogger(__name__)
        self.events: List[Tuple[str, Dict]] = []

    def publish(self, event_type: str, payload: Dict) -> bool:
        self._log.info("drainer.noop.publish %s", event_type)
        self.events.append((event_type, payload))
        return True
