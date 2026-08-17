"""Resilience primitives shared by outbound adapters.

Retry is only ever applied to operations the caller declares idempotent — a
blind retry on a non-idempotent call is worse than the original failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar

from creative_brain.domain.exceptions import ExecutionFailure
from creative_brain.ports.outbound.infrastructure import ClockPort

T = TypeVar("T")


class CircuitOpen(ExecutionFailure):
    """The circuit breaker is open and is refusing calls."""


@dataclass
class RetryPolicy:
    """Exponential backoff with a cap. ``idempotent`` gates whether retry happens at all."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    multiplier: float = 2.0

    def delay_for(self, attempt: int) -> float:
        """Backoff delay before ``attempt`` (1-based)."""
        raw = self.base_delay_seconds * (self.multiplier ** max(0, attempt - 1))
        return min(raw, self.max_delay_seconds)

    def run(
        self,
        operation: Callable[[], T],
        *,
        clock: ClockPort,
        idempotent: bool,
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> T:
        """Execute ``operation``, retrying only when it is safe to do so."""
        attempts = self.max_attempts if idempotent else 1
        last: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001 - re-raised below once budget is spent
                last = exc
                if attempt >= attempts:
                    break
                if on_retry:
                    on_retry(attempt, exc)
                clock.sleep(self.delay_for(attempt))
        raise ExecutionFailure(f"operation failed after {attempts} attempt(s): {last}") from last


@dataclass
class CircuitBreaker:
    """Stops hammering a provider that is clearly down."""

    failure_threshold: int = 5
    reset_after_seconds: float = 60.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def allow(self, *, clock: ClockPort) -> bool:
        """Whether a call may proceed right now."""
        if self._opened_at is None:
            return True
        if clock.now().timestamp() - self._opened_at >= self.reset_after_seconds:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        """Reset the failure counter."""
        self._failures = 0
        self._opened_at = None

    def record_failure(self, *, clock: ClockPort) -> None:
        """Count a failure and open the circuit once the threshold is crossed."""
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = clock.now().timestamp()

    @property
    def is_open(self) -> bool:
        """Whether the breaker is currently refusing calls."""
        return self._opened_at is not None


@dataclass
class RateLimiter:
    """A simple token bucket over the injected clock.

    ``max_calls <= 0`` means unlimited: used when no external provider is being
    protected (mock mode), where throttling would only waste wall-clock time.
    """

    max_calls: int = 60
    per_seconds: float = 60.0
    _timestamps: list[float] = field(default_factory=list, init=False)

    @property
    def is_unlimited(self) -> bool:
        """Whether this limiter lets everything through."""
        return self.max_calls <= 0

    def acquire(self, *, clock: ClockPort) -> None:
        """Block (via the clock) until a slot is available."""
        if self.is_unlimited:
            return
        now = clock.now().timestamp()
        self._timestamps = [t for t in self._timestamps if now - t < self.per_seconds]
        if len(self._timestamps) >= self.max_calls:
            oldest = min(self._timestamps)
            clock.sleep(max(0.0, self.per_seconds - (now - oldest)))
            now = clock.now().timestamp()
            self._timestamps = [t for t in self._timestamps if now - t < self.per_seconds]
        self._timestamps.append(now)

    def remaining(self, *, clock: ClockPort) -> int:
        """How many calls are still allowed in the current window."""
        if self.is_unlimited:
            return self.max_calls if self.max_calls > 0 else 2**31
        now = clock.now().timestamp()
        active = [t for t in self._timestamps if now - t < self.per_seconds]
        return max(0, self.max_calls - len(active))


__all__ = ["CircuitBreaker", "CircuitOpen", "RateLimiter", "RetryPolicy"]
