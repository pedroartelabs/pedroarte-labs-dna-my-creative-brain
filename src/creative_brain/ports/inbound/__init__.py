"""Inbound ports — how the outside world drives the creative mind.

The CLI (and any future HTTP API or dashboard) is an *adapter* that speaks
through these. Business rules never live in a route handler or an argparse
callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    """What ``creative-brain status`` renders."""

    running: bool
    phase: str
    cycle_number: int
    cycle_id: str
    energy: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    current_focus: str = ""
    next_decision: str = "dynamic"
    dream_mode: str = "scheduled dynamically"
    last_winner: str = ""
    llm_calls: int = 0
    estimated_cost_usd: float = 0.0


@runtime_checkable
class RuntimeControlPort(Protocol):
    """Start, stop and inspect the autonomous runtime."""

    def start(self, *, cycles: int | None = None) -> None:
        """Run the autonomous loop, optionally bounded to ``cycles`` cycles."""
        ...

    def run_single_cycle(self) -> dict[str, Any]:
        """Execute exactly one full circadian cycle and return its summary."""
        ...

    def stop(self) -> None:
        """Request a graceful shutdown."""
        ...

    def status(self) -> RuntimeStatus:
        """Current state of the mind."""
        ...


@runtime_checkable
class InspectionPort(Protocol):
    """Read-only views used by the CLI to inspect memory, graveyard and tournaments."""

    def inspect_memory(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent memory records."""
        ...

    def inspect_graveyard(self, limit: int = 20) -> list[dict[str, Any]]:
        """Buried ideas and why they died."""
        ...

    def inspect_tournament(self, tournament_id: str | None = None) -> dict[str, Any]:
        """One tournament's rounds and outcome (the latest, by default)."""
        ...

    def list_agents(self) -> list[dict[str, Any]]:
        """Every registered agent and its decision rights."""
        ...

    def clock_status(self) -> dict[str, Any]:
        """The circadian state and the reasoning behind the last decision."""
        ...


__all__ = ["InspectionPort", "RuntimeControlPort", "RuntimeStatus"]
