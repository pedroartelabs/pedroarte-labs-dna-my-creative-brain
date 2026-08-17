"""Event bus adapters.

The in-memory bus is deliberately the only implementation for v1: a simple
core with an extensible architecture beats a Kafka dependency nobody needs yet.
Redis/Kafka/NATS slot in behind the same port.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Sequence

from creative_brain.domain.events import DomainEvent

Handler = Callable[[DomainEvent], None]


class InMemoryEventBus:
    """Synchronous pub/sub with a dead-letter path for repeatedly failing handlers."""

    def __init__(self, *, max_retries: int = 2, dead_letter_dir: Path | None = None) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._history: list[DomainEvent] = []
        self._dead_letters: list[dict[str, Any]] = []
        self._max_retries = max_retries
        self._dead_letter_dir = dead_letter_dir

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register a handler. ``'*'`` subscribes to every event."""
        self._handlers[event_name].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Deliver one event, isolating handler failures from the creative loop."""
        self._history.append(event)
        for handler in (*self._handlers.get(str(event.name), ()), *self._handlers.get("*", ())):
            self._dispatch(handler, event)

    def publish_all(self, events: Sequence[DomainEvent]) -> None:
        """Deliver a batch in order."""
        for event in events:
            self.publish(event)

    def history(self) -> list[DomainEvent]:
        """Every event published in this process."""
        return list(self._history)

    def dead_letters(self) -> list[dict[str, Any]]:
        """Events whose handler failed every retry."""
        return list(self._dead_letters)

    def clear(self) -> None:
        """Drop history (not subscriptions). Used between cycles under test."""
        self._history.clear()

    def _dispatch(self, handler: Handler, event: DomainEvent) -> None:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                handler(event)
                return
            except Exception as exc:  # noqa: BLE001 - a bad handler must not kill the cycle
                last_error = exc
        self._to_dead_letter(event, handler, last_error)

    def _to_dead_letter(
        self, event: DomainEvent, handler: Handler, error: Exception | None
    ) -> None:
        entry = {
            "event": event.as_dict(),
            "handler": getattr(handler, "__qualname__", repr(handler)),
            "error": f"{type(error).__name__}: {error}" if error else "unknown",
        }
        self._dead_letters.append(entry)
        if self._dead_letter_dir is not None:
            self._dead_letter_dir.mkdir(parents=True, exist_ok=True)
            target = self._dead_letter_dir / f"{event.name}_{len(self._dead_letters):04d}.json"
            target.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")


__all__ = ["InMemoryEventBus"]
