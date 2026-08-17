"""Domain events.

Everything interesting that happens inside the creative mind is published as an
event. Agents never call each other directly — they react to these.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventName(StrEnum):
    """The catalogue of domain events."""

    OBSERVATION_CAPTURED = "ObservationCaptured"
    RESEARCH_COMPLETED = "ResearchCompleted"
    QUESTION_GENERATED = "QuestionGenerated"
    SEED_CREATED = "SeedCreated"
    CONCEPT_CREATED = "ConceptCreated"
    CONCEPT_ADVANCED = "ConceptAdvanced"
    CONCEPT_REJECTED = "ConceptRejected"
    CONCEPT_MUTATED = "ConceptMutated"
    CONCEPT_ENTOMBED = "ConceptEntombed"
    IDEA_RESURRECTED = "IdeaResurrected"
    CANDIDATE_SELECTED = "CandidateSelected"
    TOURNAMENT_STARTED = "TournamentStarted"
    TOURNAMENT_ROUND_FINISHED = "TournamentRoundFinished"
    TOURNAMENT_FINISHED = "TournamentFinished"
    IDEA_APPROVED = "IdeaApproved"
    IDEA_ARCHIVED = "IdeaArchived"
    PROJECT_PRODUCTION_READY = "ProjectProductionReady"
    DREAM_STARTED = "DreamStarted"
    DREAM_FINISHED = "DreamFinished"
    CIRCADIAN_PHASE_CHANGED = "CircadianPhaseChanged"
    CYCLE_STARTED = "CycleStarted"
    CYCLE_FINISHED = "CycleFinished"
    MEMORY_CONSOLIDATED = "MemoryConsolidated"
    DNA_UPDATED = "DNAUpdated"
    SATURATION_DETECTED = "SaturationDetected"
    AGENT_FAILED = "AgentFailed"
    BUDGET_EXCEEDED = "BudgetExceeded"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """An immutable fact about something that already happened."""

    name: EventName
    occurred_at: str
    cycle_id: str = ""
    correlation_id: str = ""
    subject_id: str = ""
    agent_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Serialisation-friendly view."""
        data = asdict(self)
        data["name"] = str(self.name)
        return data

    def with_correlation(self, correlation_id: str) -> DomainEvent:
        """Return a copy stamped with a trace/correlation id."""
        return DomainEvent(
            name=self.name,
            occurred_at=self.occurred_at,
            cycle_id=self.cycle_id,
            correlation_id=correlation_id,
            subject_id=self.subject_id,
            agent_id=self.agent_id,
            payload=dict(self.payload),
        )


class EventEmitter:
    """Mixin giving an aggregate a pending-event outbox.

    The aggregate records events; the application layer drains and publishes
    them. This keeps the domain free of any bus implementation.
    """

    _pending: list[DomainEvent]

    def record_event(self, event: DomainEvent) -> None:
        """Queue an event for publication."""
        if not hasattr(self, "_pending") or self._pending is None:
            self._pending = []
        self._pending.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Drain the outbox."""
        events = list(getattr(self, "_pending", []) or [])
        self._pending = []
        return events


__all__ = ["DomainEvent", "EventEmitter", "EventName"]
