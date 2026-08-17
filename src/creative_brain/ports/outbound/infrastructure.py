"""Infrastructure ports: time, randomness, scheduling, events, telemetry.

Time and randomness are ports because a creative engine that cannot be replayed
deterministically cannot be tested — and an engine that cannot be tested cannot
be trusted to run unattended.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Protocol, Sequence, TypeVar, runtime_checkable

from creative_brain.domain.events import DomainEvent

T = TypeVar("T")


@runtime_checkable
class ClockPort(Protocol):
    """The only source of 'now' in the system."""

    def now(self) -> datetime:
        """Current time."""
        ...

    def iso_now(self) -> str:
        """Current time as an ISO-8601 string, which is what entities store."""
        ...

    def sleep(self, seconds: float) -> None:
        """Pause execution (a no-op under a fake clock)."""
        ...


@runtime_checkable
class RandomPort(Protocol):
    """Controlled randomness. Randomness assists association; it never replaces reasoning."""

    def seed(self) -> int:
        """The seed in use, recorded in every cycle manifest for replayability."""
        ...

    def token(self, length: int = 8) -> str:
        """A short lowercase token used to build entity identifiers."""
        ...

    def chance(self, probability: float) -> bool:
        """True with the given probability."""
        ...

    def pick(self, items: Sequence[T]) -> T:
        """Choose one item."""
        ...

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        """Choose ``count`` distinct items (or all of them, if fewer exist)."""
        ...

    def shuffled(self, items: Sequence[T]) -> list[T]:
        """A shuffled copy."""
        ...

    def uniform(self, low: float, high: float) -> float:
        """A float in ``[low, high]``."""
        ...


@runtime_checkable
class EventBusPort(Protocol):
    """Publish/subscribe for domain events."""

    def publish(self, event: DomainEvent) -> None:
        """Deliver one event to every matching subscriber."""
        ...

    def publish_all(self, events: Sequence[DomainEvent]) -> None:
        """Deliver a batch in order."""
        ...

    def subscribe(self, event_name: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register a handler. ``'*'`` subscribes to everything."""
        ...

    def history(self) -> list[DomainEvent]:
        """Events seen so far in this process (used by the CLI and tests)."""
        ...

    def dead_letters(self) -> list[dict[str, Any]]:
        """Events whose handlers failed repeatedly."""
        ...


@runtime_checkable
class SchedulerPort(Protocol):
    """Whatever actually wakes the runtime up: in-process, cron, Celery, Temporal."""

    def schedule(self, name: str, delay_seconds: float, action: Callable[[], None]) -> None:
        """Run ``action`` once after a delay."""
        ...

    def run_pending(self) -> int:
        """Execute everything that is due. Returns how many jobs ran."""
        ...

    def cancel(self, name: str) -> bool:
        """Cancel a scheduled job."""
        ...

    def pending(self) -> list[str]:
        """Names of jobs still waiting."""
        ...


@runtime_checkable
class MetricsPort(Protocol):
    """Counters, gauges and timings."""

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Add to a counter."""
        ...

    def gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge."""
        ...

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Record a distribution sample (durations, scores)."""
        ...

    def snapshot(self) -> dict[str, Any]:
        """Everything recorded so far."""
        ...


@runtime_checkable
class LoggerPort(Protocol):
    """Structured logging with correlation ids."""

    def bind(self, **context: str) -> LoggerPort:
        """Return a logger carrying extra context on every line."""
        ...

    def debug(self, message: str, **fields: Any) -> None:
        """Debug-level line."""
        ...

    def info(self, message: str, **fields: Any) -> None:
        """Info-level line."""
        ...

    def warning(self, message: str, **fields: Any) -> None:
        """Warning-level line."""
        ...

    def error(self, message: str, **fields: Any) -> None:
        """Error-level line."""
        ...
