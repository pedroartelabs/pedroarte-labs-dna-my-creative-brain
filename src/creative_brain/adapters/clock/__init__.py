"""Clock adapters. ``FakeClock`` is what makes the whole engine testable."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta


class SystemClock:
    """Real wall-clock time."""

    def now(self) -> datetime:
        """Current UTC time."""
        return datetime.now(UTC)

    def iso_now(self) -> str:
        """Current UTC time as ISO-8601 with a ``Z`` suffix."""
        return self.now().isoformat(timespec="seconds").replace("+00:00", "Z")

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds``."""
        if seconds > 0:
            time.sleep(seconds)


class FakeClock:
    """A clock the tests own.

    Time only moves when something asks it to, so a twelve-phase circadian day
    can be executed in microseconds and asserted on exactly.
    """

    def __init__(self, start: datetime | None = None, auto_advance_seconds: float = 60.0) -> None:
        self._now = start or datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
        self._auto_advance = auto_advance_seconds
        self.slept_seconds: float = 0.0

    def now(self) -> datetime:
        """Current fake time, advancing by ``auto_advance_seconds`` on each read."""
        current = self._now
        self._now = self._now + timedelta(seconds=self._auto_advance)
        return current

    def iso_now(self) -> str:
        """Current fake time as ISO-8601."""
        return self.now().isoformat(timespec="seconds").replace("+00:00", "Z")

    def sleep(self, seconds: float) -> None:
        """Record the requested pause and jump time forward. Never actually blocks."""
        self.slept_seconds += max(0.0, seconds)
        self._now = self._now + timedelta(seconds=max(0.0, seconds))

    def advance(self, seconds: float) -> None:
        """Move time forward explicitly."""
        self._now = self._now + timedelta(seconds=seconds)


__all__ = ["FakeClock", "SystemClock"]
