"""The application context: every port and policy a use case may need.

This is the seam of the hexagon. Use cases receive this object and know only
the *contracts* inside it — never which adapter is behind them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from creative_brain.agents.society import AgentSociety
from creative_brain.domain.policies.autonomy import AutonomyPolicy
from creative_brain.domain.policies.circadian import CircadianPolicy
from creative_brain.domain.policies.constitution import ConstitutionPolicy
from creative_brain.domain.policies.dna_evolution import DnaEvolutionPolicy
from creative_brain.domain.policies.exploration import ExplorationPolicy
from creative_brain.domain.policies.memory_policy import MemoryPolicy
from creative_brain.domain.policies.mutation import MutationPolicy
from creative_brain.domain.policies.scoring import ScoringPolicy
from creative_brain.domain.services.evaluation import (
    CreativeDistanceService,
    DiversityService,
    NoveltyService,
    SaturationService,
)
from creative_brain.domain.services.tournament_service import TournamentService
from creative_brain.domain.value_objects.identifiers import EntityId
from creative_brain.ports.outbound.infrastructure import (
    ClockPort,
    EventBusPort,
    LoggerPort,
    MetricsPort,
    RandomPort,
)
from creative_brain.ports.outbound.knowledge import (
    CreativeProductionPort,
    KnowledgeGraphPort,
    KnowledgeSourcePort,
    OutputWriterPort,
    ResearchPort,
    VectorMemoryPort,
)
from creative_brain.ports.outbound.repositories import (
    AgentDecisionRepository,
    CheckpointRepository,
    CircadianStateRepository,
    ConceptRepository,
    DnaRepository,
    DreamRepository,
    MemoryRepository,
    ObservationRepository,
    ProjectRepository,
    QuestionRepository,
    ResearchRepository,
    SeedRepository,
    TournamentRepository,
)


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    """Runtime switches. Nothing important is decided by an ``if`` buried in code."""

    dream_mode_enabled: bool = True
    external_research_enabled: bool = False
    mutation_enabled: bool = True
    unknown_zone_enabled: bool = True
    production_handoff_enabled: bool = False
    lore_connections_enabled: bool = True
    meta_cognition_enabled: bool = True

    def as_dict(self) -> dict[str, bool]:
        """Serialisation-friendly view."""
        return {
            "dream_mode_enabled": self.dream_mode_enabled,
            "external_research_enabled": self.external_research_enabled,
            "mutation_enabled": self.mutation_enabled,
            "unknown_zone_enabled": self.unknown_zone_enabled,
            "production_handoff_enabled": self.production_handoff_enabled,
            "lore_connections_enabled": self.lore_connections_enabled,
            "meta_cognition_enabled": self.meta_cognition_enabled,
        }


@dataclass(frozen=True, slots=True)
class CycleTargets:
    """How much the engine tries to produce in one cycle. All configurable."""

    observations: int = 8
    questions_per_observation: int = 2
    seeds_per_generator: int = 4
    concepts: int = 12
    research_topics: int = 2
    dream_fragments: int = 5
    mutations: int = 3
    titles: int = 3

    def as_dict(self) -> dict[str, int]:
        """Serialisation-friendly view."""
        return {
            "observations": self.observations,
            "questions_per_observation": self.questions_per_observation,
            "seeds_per_generator": self.seeds_per_generator,
            "concepts": self.concepts,
            "research_topics": self.research_topics,
            "dream_fragments": self.dream_fragments,
            "mutations": self.mutations,
            "titles": self.titles,
        }


@dataclass
class Policies:
    """Every domain policy in one place, all built from configuration."""

    scoring: ScoringPolicy
    exploration: ExplorationPolicy
    circadian: CircadianPolicy
    mutation: MutationPolicy
    memory: MemoryPolicy
    dna: DnaEvolutionPolicy
    constitution: ConstitutionPolicy
    autonomy: AutonomyPolicy


@dataclass
class Services:
    """Stateless domain services."""

    novelty: NoveltyService
    distance: CreativeDistanceService
    diversity: DiversityService
    saturation: SaturationService
    tournament: TournamentService


@dataclass
class Repositories:
    """Every repository port."""

    observations: ObservationRepository
    research: ResearchRepository
    questions: QuestionRepository
    seeds: SeedRepository
    concepts: ConceptRepository
    tournaments: TournamentRepository
    projects: ProjectRepository
    memory: MemoryRepository
    dreams: DreamRepository
    dna: DnaRepository
    circadian: CircadianStateRepository
    checkpoints: CheckpointRepository
    decisions: AgentDecisionRepository


@dataclass
class BrainContext:
    """Everything a use case is allowed to touch."""

    repositories: Repositories
    policies: Policies
    services: Services
    society: AgentSociety
    clock: ClockPort
    random: RandomPort
    bus: EventBusPort
    logger: LoggerPort
    metrics: MetricsPort
    output: OutputWriterPort
    research: ResearchPort
    vectors: VectorMemoryPort
    graph: KnowledgeGraphPort
    corpus: KnowledgeSourcePort
    production: tuple[CreativeProductionPort, ...] = ()
    flags: FeatureFlags = field(default_factory=FeatureFlags)
    targets: CycleTargets = field(default_factory=CycleTargets)
    correlation_id: str = ""
    #: How far lexical measurement may pull the intended creative distance.
    distance_measurement_weight: float = 0.35

    # ------------------------------------------------------------- utilities

    def new_id(self, id_type: type[EntityId]) -> Any:
        """Mint an identifier using the injected randomness source."""
        return id_type.from_token(self.random.token(8))

    def now(self) -> str:
        """Current time as the entities store it."""
        return self.clock.iso_now()

    def publish(self, emitter: Any) -> None:
        """Drain an aggregate's outbox onto the bus, stamped with the correlation id."""
        for event in emitter.pull_events():
            self.bus.publish(event.with_correlation(self.correlation_id))

    def trace(
        self,
        *,
        who: str,
        what: str,
        why: str,
        cycle_id: str,
        inputs: tuple[str, ...] = (),
        scores: dict[str, float] | None = None,
        evidence: tuple[str, ...] = (),
    ) -> None:
        """Persist a decision trace. Article 14: decisions must stay explainable."""
        self.repositories.decisions.add(
            {
                "who": who,
                "what": what,
                "why": why,
                "decided_at": self.now(),
                "inputs": list(inputs),
                "scores": scores or {},
                "evidence": list(evidence),
                "cycle_id": cycle_id,
                "correlation_id": self.correlation_id,
            }
        )


__all__ = [
    "BrainContext",
    "CycleTargets",
    "FeatureFlags",
    "Policies",
    "Repositories",
    "Services",
]
