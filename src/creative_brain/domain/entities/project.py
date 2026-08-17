"""An approved idea promoted to a project, plus its production manifest."""

from __future__ import annotations

from dataclasses import dataclass, field

from creative_brain.domain.entities.agent_opinion import DecisionTrace
from creative_brain.domain.events import DomainEvent, EventEmitter, EventName
from creative_brain.domain.exceptions import DomainRuleViolation
from creative_brain.domain.value_objects.genome import CreativeGenome
from creative_brain.domain.value_objects.identifiers import ProjectId
from creative_brain.domain.value_objects.scores import ScoreBoard

#: Downstream engines this repository is designed to hand work off to.
KNOWN_ENGINES = (
    "living_book_engine",
    "youtube_living_book_engine",
    "living_sound_engine",
    "game_engine",
    "site_engine",
)


@dataclass(slots=True)
class CreativeProject(EventEmitter):
    """A tournament winner, packaged with everything a production engine needs."""

    id: ProjectId
    concept_id: str
    title: str
    logline: str
    central_question: str
    genome: CreativeGenome
    created_at: str
    cycle_id: str = ""
    status: str = "APPROVED"
    scoreboard: ScoreBoard = field(default_factory=lambda: ScoreBoard({}))
    total_score: float = 0.0
    artifacts: dict[str, str] = field(default_factory=dict)
    decision_traces: list[DecisionTrace] = field(default_factory=list)
    recommended_engines: tuple[str, ...] = ()
    _pending: list[DomainEvent] = field(default_factory=list, repr=False)

    def mark_production_ready(self, *, at: str, engines: tuple[str, ...]) -> None:
        """Declare the project ready for hand-off to a production engine."""
        unknown = [e for e in engines if e not in KNOWN_ENGINES]
        if unknown:
            raise DomainRuleViolation(f"unknown production engines: {unknown}")
        if not self.artifacts:
            raise DomainRuleViolation("a production-ready project must carry artifacts")
        self.status = "PRODUCTION_READY"
        self.recommended_engines = engines
        self.record_event(
            DomainEvent(
                name=EventName.PROJECT_PRODUCTION_READY,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={"title": self.title, "engines": list(engines)},
            )
        )

    def add_trace(self, trace: DecisionTrace) -> None:
        """Attach a decision trace so the choice stays explainable years later."""
        self.decision_traces.append(trace)

    def execution_manifest(self) -> dict[str, object]:
        """The hand-off contract consumed by downstream production engines."""
        return {
            "project_id": str(self.id),
            "concept_id": self.concept_id,
            "title": self.title,
            "logline": self.logline,
            "central_question": self.central_question,
            "status": self.status,
            "created_at": self.created_at,
            "cycle_id": self.cycle_id,
            "recommended_engines": list(self.recommended_engines),
            "creative_scores": {**self.scoreboard.as_dict(), "total": self.total_score},
            "creative_genome": self.genome.as_dict(),
            "artifacts": sorted(self.artifacts),
        }

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            **self.execution_manifest(),
            "artifact_bodies": dict(self.artifacts),
            "decision_traces": [t.as_dict() for t in self.decision_traces],
        }
