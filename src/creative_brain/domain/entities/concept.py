"""The central aggregate: a creative concept walking its lifecycle.

A concept is born as a SEED and either reaches PRODUCTION_READY or ends in the
GRAVEYARD — but it is never deleted. Every stage change is guarded by the
lifecycle policy and recorded as a domain event.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from creative_brain.domain.entities.agent_opinion import AgentOpinion, Verdict
from creative_brain.domain.events import DomainEvent, EventEmitter, EventName
from creative_brain.domain.exceptions import DomainRuleViolation
from creative_brain.domain.policies.lifecycle import (
    CreativeStage,
    assert_transition,
    is_alive,
)
from creative_brain.domain.value_objects.creative_distance import CreativeDistance
from creative_brain.domain.value_objects.genome import CreativeGenome, GenomeOrigin
from creative_brain.domain.value_objects.identifiers import ConceptId
from creative_brain.domain.value_objects.lineage import Lineage, LineageRelation
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard

#: Named prose artifacts a concept accumulates as it advances.
ARTIFACT_KEYS = (
    "concept",
    "premise",
    "pitch",
    "synopsis",
    "world_bible",
    "characters",
    "central_question",
)


@dataclass(slots=True)
class CreativeConcept(EventEmitter):
    """An idea with a title, a mechanism, a lifecycle and a memory of its own trial."""

    id: ConceptId
    title: str
    logline: str
    genome: CreativeGenome
    created_at: str
    updated_at: str = ""
    stage: CreativeStage = CreativeStage.SEED
    cycle_id: str = ""
    seed_id: str = ""
    question_id: str = ""
    central_question: str = ""
    themes: tuple[str, ...] = ()
    lineage: Lineage = field(default_factory=Lineage)
    scoreboard: ScoreBoard = field(default_factory=lambda: ScoreBoard({}))
    opinions: list[AgentOpinion] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    rejection_reasons: tuple[str, ...] = ()
    mutation_potential: float = 50.0
    total_score: CreativeScore = field(default_factory=CreativeScore.zero)
    rejected_at: str = ""
    _pending: list[DomainEvent] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------ build

    @classmethod
    def germinate(
        cls,
        *,
        concept_id: ConceptId,
        title: str,
        logline: str,
        origin: GenomeOrigin,
        at: str,
        cycle_id: str = "",
        seed_id: str = "",
        question_id: str = "",
        themes: tuple[str, ...] = (),
        tone: tuple[str, ...] = (),
        structure: tuple[str, ...] = (),
        lineage: Lineage | None = None,
    ) -> CreativeConcept:
        """Create a brand-new concept in the SEED stage."""
        if not title.strip():
            raise DomainRuleViolation("a concept cannot exist without a title")
        concept = cls(
            id=concept_id,
            title=title.strip(),
            logline=logline.strip(),
            genome=CreativeGenome(origin=origin, themes=themes, tone=tone, structure=structure),
            created_at=at,
            updated_at=at,
            cycle_id=cycle_id,
            seed_id=seed_id,
            question_id=question_id,
            themes=themes,
            lineage=lineage or Lineage(),
        )
        concept.record_event(
            DomainEvent(
                name=EventName.CONCEPT_CREATED,
                occurred_at=at,
                cycle_id=cycle_id,
                subject_id=str(concept_id),
                payload={
                    "title": concept.title,
                    "mechanism": str(origin.mechanism),
                    "seed_id": seed_id,
                },
            )
        )
        return concept

    # -------------------------------------------------------------- lifecycle

    def advance_to(self, target: CreativeStage, *, at: str, reason: str = "") -> None:
        """Move one step forward on the main line, enforcing the state machine."""
        assert_transition(f"concept:{self.id}", self.stage, target)
        source, self.stage = self.stage, target
        self.updated_at = at
        self.record_event(
            DomainEvent(
                name=EventName.CONCEPT_ADVANCED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={"from": str(source), "to": str(target), "reason": reason},
            )
        )
        if target is CreativeStage.CANDIDATE:
            self.record_event(
                DomainEvent(
                    name=EventName.CANDIDATE_SELECTED,
                    occurred_at=at,
                    cycle_id=self.cycle_id,
                    subject_id=str(self.id),
                    payload={"title": self.title, "score": self.total_score.value},
                )
            )
        if target is CreativeStage.APPROVED:
            self.record_event(
                DomainEvent(
                    name=EventName.IDEA_APPROVED,
                    occurred_at=at,
                    cycle_id=self.cycle_id,
                    subject_id=str(self.id),
                    payload={"title": self.title, "score": self.total_score.value},
                )
            )

    def reject(self, reasons: tuple[str, ...], *, at: str, by: str = "CREATIVE_JUDGE_AGENT") -> None:
        """Send the idea off the main line, preserving why it died."""
        assert_transition(f"concept:{self.id}", self.stage, CreativeStage.REJECTED)
        if not reasons:
            raise DomainRuleViolation("a rejection must state at least one reason")
        self.stage = CreativeStage.REJECTED
        self.rejection_reasons = reasons
        self.rejected_at = at
        self.updated_at = at
        self.record_event(
            DomainEvent(
                name=EventName.CONCEPT_REJECTED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                agent_id=by,
                payload={"title": self.title, "reasons": list(reasons)},
            )
        )

    def entomb(self, *, at: str) -> None:
        """Move a rejected/archived idea into the graveyard. Nothing is ever erased."""
        assert_transition(f"concept:{self.id}", self.stage, CreativeStage.GRAVEYARD)
        self.stage = CreativeStage.GRAVEYARD
        self.updated_at = at
        self.record_event(
            DomainEvent(
                name=EventName.CONCEPT_ENTOMBED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={"title": self.title, "mutation_potential": self.mutation_potential},
            )
        )

    def send_to_mutation_pool(self, *, at: str) -> None:
        """Mark the idea as available for the mutation engine."""
        assert_transition(f"concept:{self.id}", self.stage, CreativeStage.MUTATION_POOL)
        self.stage = CreativeStage.MUTATION_POOL
        self.updated_at = at

    def archive(self, *, at: str, reason: str = "") -> None:
        """Park the idea without judging it as bad."""
        assert_transition(f"concept:{self.id}", self.stage, CreativeStage.ARCHIVED)
        self.stage = CreativeStage.ARCHIVED
        self.updated_at = at
        self.record_event(
            DomainEvent(
                name=EventName.IDEA_ARCHIVED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={"title": self.title, "reason": reason},
            )
        )

    def sleep(self, *, at: str) -> None:
        """Park the idea until a later cycle looks at it with fresh eyes."""
        assert_transition(f"concept:{self.id}", self.stage, CreativeStage.SLEEPING)
        self.stage = CreativeStage.SLEEPING
        self.updated_at = at

    def resurrect_as(
        self, *, concept_id: ConceptId, at: str, note: str, cycle_id: str
    ) -> CreativeConcept:
        """Copy this dead idea into a fresh lineage. The original stays buried."""
        revived = CreativeConcept(
            id=concept_id,
            title=self.title,
            logline=self.logline,
            genome=self.genome,
            created_at=at,
            updated_at=at,
            stage=CreativeStage.MUTATION_POOL,
            cycle_id=cycle_id,
            seed_id=self.seed_id,
            question_id=self.question_id,
            central_question=self.central_question,
            themes=self.themes,
            lineage=self.lineage.add(LineageRelation.RESURRECTED_FROM, str(self.id), note),
            artifacts=dict(self.artifacts),
            mutation_potential=self.mutation_potential,
        )
        revived.record_event(
            DomainEvent(
                name=EventName.IDEA_RESURRECTED,
                occurred_at=at,
                cycle_id=cycle_id,
                subject_id=str(concept_id),
                payload={"source_id": str(self.id), "title": self.title, "note": note},
            )
        )
        return revived

    # ------------------------------------------------------------- evaluation

    def add_opinion(self, opinion: AgentOpinion) -> None:
        """Attach one agent's structured judgement."""
        self.opinions.append(opinion)
        if opinion.scores.scores:
            self.scoreboard = self.scoreboard.merge(opinion.scores)

    def apply_total(self, total: CreativeScore, *, at: str) -> None:
        """Record the weighted aggregate produced by the scoring policy."""
        self.total_score = total
        self.updated_at = at

    def apply_evaluation(
        self,
        *,
        novelty: CreativeScore | None = None,
        commercial: CreativeScore | None = None,
        identity: CreativeScore | None = None,
        distance: CreativeDistance | None = None,
    ) -> None:
        """Fold evaluation results into the genome."""
        self.genome = self.genome.with_scores(
            novelty=novelty, commercial=commercial, identity=identity, distance=distance
        )

    def attach(self, key: str, content: str) -> None:
        """Store a prose artifact (premise, pitch, synopsis, world bible, ...)."""
        if key not in ARTIFACT_KEYS:
            raise DomainRuleViolation(f"unknown artifact '{key}'; expected one of {ARTIFACT_KEYS}")
        self.artifacts[key] = content
        if key == "central_question":
            self.central_question = content

    def record_mutation(self, *, at: str, operator: str, parent_id: str) -> None:
        """Mark this concept as the product of a mutation of ``parent_id``."""
        self.lineage = self.lineage.add(LineageRelation.MUTATED_FROM, parent_id, operator)
        self.updated_at = at
        self.record_event(
            DomainEvent(
                name=EventName.CONCEPT_MUTATED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={"operator": operator, "parent_id": parent_id, "title": self.title},
            )
        )

    # ---------------------------------------------------------------- queries

    @property
    def is_alive(self) -> bool:
        """Whether the concept is still on the main competitive line."""
        return is_alive(self.stage)

    @property
    def is_blocked(self) -> bool:
        """Whether any agent issued a confident rejection."""
        return any(o.is_blocking for o in self.opinions)

    @property
    def support_ratio(self) -> float:
        """Share of non-abstaining agents that support the idea, 0..1."""
        voting = [o for o in self.opinions if o.verdict is not Verdict.ABSTAIN]
        if not voting:
            return 0.0
        return sum(1 for o in voting if o.verdict is Verdict.SUPPORT) / len(voting)

    @property
    def disagreement(self) -> float:
        """0 when the society is unanimous, 1 at maximum split."""
        ratio = self.support_ratio
        return round(1.0 - abs(2 * ratio - 1.0), 4)

    def opinion_of(self, agent: str) -> AgentOpinion | None:
        """Fetch a specific agent's opinion if it exists."""
        return next((o for o in self.opinions if o.agent == agent), None)

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "title": self.title,
            "logline": self.logline,
            "stage": str(self.stage),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "rejected_at": self.rejected_at,
            "cycle_id": self.cycle_id,
            "seed_id": self.seed_id,
            "question_id": self.question_id,
            "central_question": self.central_question,
            "themes": list(self.themes),
            "genome": self.genome.as_dict(),
            "lineage": self.lineage.as_list(),
            "scores": self.scoreboard.as_dict(),
            "total_score": self.total_score.value,
            "opinions": [o.as_dict() for o in self.opinions],
            "artifacts": dict(self.artifacts),
            "rejection_reasons": list(self.rejection_reasons),
            "mutation_potential": self.mutation_potential,
            "support_ratio": self.support_ratio,
            "disagreement": self.disagreement,
        }
