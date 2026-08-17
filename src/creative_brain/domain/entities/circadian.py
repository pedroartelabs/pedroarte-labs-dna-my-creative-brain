"""The artificial circadian rhythm.

The clock owns **WHEN**. Every other agent owns WHAT, HOW and WHY. This module
holds the phase vocabulary and the mutable state the policy reads; the decision
logic itself lives in ``domain/policies/circadian.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from creative_brain.domain.events import DomainEvent, EventEmitter, EventName
from creative_brain.domain.value_objects.energy import EnergyKind, EnergyProfile


class BiologicalPhase(StrEnum):
    """The phases of one artificial creative day."""

    AWAKENING = "AWAKENING"
    OBSERVATION = "OBSERVATION"
    HUNT = "HUNT"
    FOCUS = "FOCUS"
    CREATION = "CREATION"
    DIGESTION = "DIGESTION"
    REFLECTION = "REFLECTION"
    SECOND_WIND = "SECOND_WIND"
    EXPLORATION = "EXPLORATION"
    CONSOLIDATION = "CONSOLIDATION"
    DREAMING = "DREAMING"
    DEEP_SLEEP = "DEEP_SLEEP"


#: The canonical ordering used as a fallback when no signal dominates.
PHASE_ORDER: tuple[BiologicalPhase, ...] = (
    BiologicalPhase.AWAKENING,
    BiologicalPhase.OBSERVATION,
    BiologicalPhase.HUNT,
    BiologicalPhase.FOCUS,
    BiologicalPhase.CREATION,
    BiologicalPhase.DIGESTION,
    BiologicalPhase.REFLECTION,
    BiologicalPhase.SECOND_WIND,
    BiologicalPhase.EXPLORATION,
    BiologicalPhase.CONSOLIDATION,
    BiologicalPhase.DREAMING,
    BiologicalPhase.DEEP_SLEEP,
)

#: Phases during which no new work may be approved or started (article: rest is real).
QUIET_PHASES: frozenset[BiologicalPhase] = frozenset({BiologicalPhase.DEEP_SLEEP})

#: Which gauge each phase mainly consumes, and how much per execution.
PHASE_COST: dict[BiologicalPhase, tuple[EnergyKind, float]] = {
    BiologicalPhase.AWAKENING: (EnergyKind.CREATIVE, 2.0),
    BiologicalPhase.OBSERVATION: (EnergyKind.RESEARCH, 12.0),
    BiologicalPhase.HUNT: (EnergyKind.RESEARCH, 25.0),
    BiologicalPhase.FOCUS: (EnergyKind.CRITICAL, 10.0),
    BiologicalPhase.CREATION: (EnergyKind.CREATIVE, 30.0),
    BiologicalPhase.DIGESTION: (EnergyKind.CRITICAL, 8.0),
    BiologicalPhase.REFLECTION: (EnergyKind.CRITICAL, 20.0),
    BiologicalPhase.SECOND_WIND: (EnergyKind.CREATIVE, 22.0),
    BiologicalPhase.EXPLORATION: (EnergyKind.CREATIVE, 18.0),
    BiologicalPhase.CONSOLIDATION: (EnergyKind.CRITICAL, 15.0),
    BiologicalPhase.DREAMING: (EnergyKind.CREATIVE, 8.0),
    BiologicalPhase.DEEP_SLEEP: (EnergyKind.CREATIVE, 0.0),
}


@dataclass(frozen=True, slots=True)
class CircadianDecision:
    """The clock's answer to "what should the mind do next, and for how long"."""

    phase: BiologicalPhase
    reason: str
    decided_at: str
    duration_seconds: float = 0.0
    signals: dict[str, float] = field(default_factory=dict)
    ends_cycle: bool = False

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "phase": str(self.phase),
            "reason": self.reason,
            "decided_at": self.decided_at,
            "duration_seconds": self.duration_seconds,
            "signals": dict(self.signals),
            "ends_cycle": self.ends_cycle,
        }


@dataclass(slots=True)
class CircadianState(EventEmitter):
    """Everything the circadian policy needs to decide the next phase."""

    cycle_number: int = 0
    cycle_id: str = ""
    phase: BiologicalPhase = BiologicalPhase.DEEP_SLEEP
    phase_started_at: str = ""
    energy: EnergyProfile = field(default_factory=EnergyProfile.rested)

    # --- backlogs the policy reads ---
    observation_backlog: int = 0
    research_backlog: int = 0
    seed_backlog: int = 0
    concept_backlog: int = 0
    unconsolidated_events: int = 0
    graveyard_size: int = 0
    unfinished_cycles: int = 0

    # --- quality signals ---
    recent_novelty: float = 50.0
    recent_quality: float = 50.0
    duplicate_rate: float = 0.0
    failure_rate: float = 0.0

    # --- budgets ---
    llm_calls_this_cycle: int = 0
    research_calls_this_cycle: int = 0
    estimated_cost_usd: float = 0.0

    phases_visited: tuple[str, ...] = ()
    history: list[dict[str, object]] = field(default_factory=list)
    _pending: list[DomainEvent] = field(default_factory=list, repr=False)

    # ---------------------------------------------------------------- mutate

    def enter(self, decision: CircadianDecision) -> None:
        """Move into the decided phase, spending the matching energy gauge."""
        previous = self.phase
        self.phase = decision.phase
        self.phase_started_at = decision.decided_at
        self.phases_visited = (*self.phases_visited, str(decision.phase))
        kind, cost = PHASE_COST[decision.phase]
        if cost:
            self.energy = self.energy.spend(kind, cost)
        self.history.append(decision.as_dict())
        self.record_event(
            DomainEvent(
                name=EventName.CIRCADIAN_PHASE_CHANGED,
                occurred_at=decision.decided_at,
                cycle_id=self.cycle_id,
                agent_id="BIOLOGICAL_CLOCK_AGENT",
                payload={
                    "from": str(previous),
                    "to": str(decision.phase),
                    "reason": decision.reason,
                    "signals": decision.signals,
                },
            )
        )

    def begin_cycle(self, *, cycle_id: str, at: str) -> None:
        """Start a new creative day, resetting per-cycle counters."""
        self.cycle_number += 1
        self.cycle_id = cycle_id
        self.phases_visited = ()
        self.llm_calls_this_cycle = 0
        self.research_calls_this_cycle = 0
        self.estimated_cost_usd = 0.0
        self.record_event(
            DomainEvent(
                name=EventName.CYCLE_STARTED,
                occurred_at=at,
                cycle_id=cycle_id,
                agent_id="BIOLOGICAL_CLOCK_AGENT",
                payload={"cycle_number": self.cycle_number},
            )
        )

    def end_cycle(self, *, at: str) -> None:
        """Close the creative day and restore the gauges through sleep."""
        self.energy = self.energy.restored_by_sleep()
        self.unconsolidated_events = 0
        self.record_event(
            DomainEvent(
                name=EventName.CYCLE_FINISHED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                agent_id="BIOLOGICAL_CLOCK_AGENT",
                payload={
                    "cycle_number": self.cycle_number,
                    "phases": list(self.phases_visited),
                    "llm_calls": self.llm_calls_this_cycle,
                    "estimated_cost_usd": round(self.estimated_cost_usd, 6),
                },
            )
        )

    def with_energy(self, energy: EnergyProfile) -> CircadianState:
        """Return a copy carrying a different energy profile (used by policies/tests)."""
        return replace(self, energy=energy)

    # ---------------------------------------------------------------- queries

    @property
    def has_visited(self) -> frozenset[str]:
        """Phases already executed in the current cycle."""
        return frozenset(self.phases_visited)

    def visited(self, phase: BiologicalPhase) -> bool:
        """Whether ``phase`` already ran in this cycle."""
        return str(phase) in self.has_visited

    @property
    def is_quiet(self) -> bool:
        """Whether the engine is currently in a phase that forbids new approvals."""
        return self.phase in QUIET_PHASES

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view used for checkpointing."""
        return {
            "cycle_number": self.cycle_number,
            "cycle_id": self.cycle_id,
            "phase": str(self.phase),
            "phase_started_at": self.phase_started_at,
            "energy": self.energy.as_dict(),
            "observation_backlog": self.observation_backlog,
            "research_backlog": self.research_backlog,
            "seed_backlog": self.seed_backlog,
            "concept_backlog": self.concept_backlog,
            "unconsolidated_events": self.unconsolidated_events,
            "graveyard_size": self.graveyard_size,
            "unfinished_cycles": self.unfinished_cycles,
            "recent_novelty": self.recent_novelty,
            "recent_quality": self.recent_quality,
            "duplicate_rate": self.duplicate_rate,
            "failure_rate": self.failure_rate,
            "llm_calls_this_cycle": self.llm_calls_this_cycle,
            "research_calls_this_cycle": self.research_calls_this_cycle,
            "estimated_cost_usd": self.estimated_cost_usd,
            "phases_visited": list(self.phases_visited),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> CircadianState:
        """Rebuild persisted state on resume."""
        state = cls()
        state.cycle_number = int(raw.get("cycle_number", 0) or 0)
        state.cycle_id = str(raw.get("cycle_id", "") or "")
        state.phase = BiologicalPhase(str(raw.get("phase", BiologicalPhase.DEEP_SLEEP)))
        state.phase_started_at = str(raw.get("phase_started_at", "") or "")
        energy = raw.get("energy")
        if isinstance(energy, dict):
            state.energy = EnergyProfile.from_mapping({k: float(v) for k, v in energy.items()})
        for key in (
            "observation_backlog",
            "research_backlog",
            "seed_backlog",
            "concept_backlog",
            "unconsolidated_events",
            "graveyard_size",
            "unfinished_cycles",
            "llm_calls_this_cycle",
            "research_calls_this_cycle",
        ):
            setattr(state, key, int(raw.get(key, 0) or 0))
        for key in (
            "recent_novelty",
            "recent_quality",
            "duplicate_rate",
            "failure_rate",
            "estimated_cost_usd",
        ):
            setattr(state, key, float(raw.get(key, 0.0) or 0.0))
        visited = raw.get("phases_visited")
        if isinstance(visited, list):
            state.phases_visited = tuple(str(p) for p in visited)
        return state
