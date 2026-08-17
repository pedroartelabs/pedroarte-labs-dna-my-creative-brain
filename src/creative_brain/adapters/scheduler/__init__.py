"""Scheduler adapters.

The runtime does not know what wakes it up. Today it is an in-process
scheduler driven by the clock port; tomorrow it can be APScheduler, cron,
Celery or Temporal without the domain noticing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from creative_brain.ports.outbound.infrastructure import ClockPort


@dataclass(order=True)
class _Job:
    due_at: float
    name: str = field(compare=False)
    action: Callable[[], None] = field(compare=False)


class InProcessScheduler:
    """A minimal scheduler driven by the injected clock, not by ``time.sleep``."""

    def __init__(self, clock: ClockPort) -> None:
        self._clock = clock
        self._jobs: list[_Job] = []

    def schedule(self, name: str, delay_seconds: float, action: Callable[[], None]) -> None:
        """Run ``action`` once, ``delay_seconds`` from now. Re-scheduling replaces the job."""
        self.cancel(name)
        due = self._clock.now().timestamp() + max(0.0, delay_seconds)
        self._jobs.append(_Job(due_at=due, name=name, action=action))
        self._jobs.sort()

    def run_pending(self) -> int:
        """Execute everything due. Returns how many jobs ran."""
        now = self._clock.now().timestamp()
        due = [job for job in self._jobs if job.due_at <= now]
        self._jobs = [job for job in self._jobs if job.due_at > now]
        for job in due:
            job.action()
        return len(due)

    def cancel(self, name: str) -> bool:
        """Cancel a job by name."""
        before = len(self._jobs)
        self._jobs = [job for job in self._jobs if job.name != name]
        return len(self._jobs) < before

    def pending(self) -> list[str]:
        """Names of jobs still waiting, soonest first."""
        return [job.name for job in sorted(self._jobs)]


__all__ = ["InProcessScheduler"]
