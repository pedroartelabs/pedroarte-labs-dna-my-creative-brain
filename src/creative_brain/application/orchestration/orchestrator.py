"""The creative orchestrator.

It coordinates; it does not decide. Every business rule lives in the domain
policies, and every unit of work is a use case. The orchestrator's only job is
to know which use cases belong to which circadian phase, and to keep the
circadian state honest about what the mind just did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from creative_brain.application.context import BrainContext
from creative_brain.application.orchestration.artifacts import CycleArtifactWriter
from creative_brain.application.use_cases import (
    AnalyseObsessions,
    ApproveCreativeProject,
    BuildCreativeConcepts,
    CaptureObservation,
    ConsolidateMemory,
    DevelopWinner,
    EvaluateConcepts,
    GenerateCreativeQuestions,
    GenerateCreativeSeeds,
    JudgeFinalists,
    MutateRejectedConcepts,
    RunCreativeTournament,
    RunMetaCognition,
    RunResearch,
    StartDreamCycle,
    UpdateEvolvingDna,
)
from creative_brain.domain.entities.circadian import BiologicalPhase, CircadianState
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.tournament import TournamentFunnel
from creative_brain.domain.exceptions import EmptyTournamentError
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.energy import EnergyKind


@dataclass
class CycleOutcome:
    """What one cycle produced. Returned by ``--single-cycle`` and the demo."""

    cycle_id: str
    winner_title: str = ""
    winner_id: str = ""
    project_id: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    diversity: float = 0.0
    dna_version: int = 0
    phases: list[str] = field(default_factory=list)
    focus: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serialisation-friendly view."""
        return {
            "cycle_id": self.cycle_id,
            "winner_title": self.winner_title,
            "winner_id": self.winner_id,
            "project_id": self.project_id,
            "counts": dict(self.counts),
            "diversity": self.diversity,
            "dna_version": self.dna_version,
            "phases": list(self.phases),
            "focus": self.focus,
        }


@dataclass
class CreativeOrchestrator:
    """Executes one circadian phase at a time against the shared cycle state."""

    context: BrainContext
    funnel: TournamentFunnel
    artifacts: CycleArtifactWriter = field(init=False)
    outcome: CycleOutcome = field(init=False)

    def __post_init__(self) -> None:
        self.artifacts = CycleArtifactWriter(self.context)
        self.outcome = CycleOutcome(cycle_id="")

    # ------------------------------------------------------------ cycle glue

    def begin_cycle(self, state: CircadianState, cycle_id: str) -> None:
        """Open a new creative day."""
        self.outcome = CycleOutcome(cycle_id=cycle_id)
        state.begin_cycle(cycle_id=cycle_id, at=self.context.now())
        self.context.publish(state)

    def execute_phase(self, phase: BiologicalPhase, state: CircadianState) -> None:
        """Run the work that belongs to ``phase`` and refresh the clock's signals."""
        handler = self._handlers().get(phase)
        if handler is None:
            return
        started = self.context.clock.now().timestamp()
        handler(state)
        self.context.metrics.observe(
            "circadian_phase_duration",
            max(0.0, self.context.clock.now().timestamp() - started),
            phase=str(phase),
        )
        self._refresh_signals(state)

    def _handlers(self) -> dict[BiologicalPhase, Any]:
        return {
            BiologicalPhase.AWAKENING: self._awaken,
            BiologicalPhase.OBSERVATION: self._observe,
            BiologicalPhase.HUNT: self._hunt,
            BiologicalPhase.FOCUS: self._focus,
            BiologicalPhase.CREATION: self._create,
            BiologicalPhase.DIGESTION: self._digest,
            BiologicalPhase.REFLECTION: self._reflect,
            BiologicalPhase.SECOND_WIND: self._second_wind,
            BiologicalPhase.EXPLORATION: self._explore,
            BiologicalPhase.CONSOLIDATION: self._consolidate,
            BiologicalPhase.DREAMING: self._dream,
            BiologicalPhase.DEEP_SLEEP: self._deep_sleep,
        }

    # --------------------------------------------------------------- phases

    def _awaken(self, state: CircadianState) -> None:
        """Reload context, restore state, read the previous cycle."""
        ctx = self.context
        ctx.corpus.ingest()
        evolving = ctx.repositories.dna.load_evolving()
        previous = ctx.repositories.projects.list_all(limit=1)
        self.outcome.focus = (
            evolving.promising_territories[-1]
            if evolving.promising_territories
            else "território ainda não definido"
        )
        ctx.logger.info(
            "phase.awakening",
            cycle_id=state.cycle_id,
            dna_version=evolving.version,
            last_winner=previous[0].title if previous else "",
            focus=self.outcome.focus,
        )

    def _observe(self, state: CircadianState) -> None:
        CaptureObservation(self.context).execute(cycle_id=state.cycle_id, focus=self.outcome.focus)

    def _hunt(self, state: CircadianState) -> None:
        RunResearch(self.context).execute(cycle_id=state.cycle_id)

    def _focus(self, state: CircadianState) -> None:
        """Narrow down: turn observations into questions and pick the cycle's focus."""
        questions = GenerateCreativeQuestions(self.context).execute(cycle_id=state.cycle_id)
        if questions:
            self.outcome.focus = questions[0].text

    def _create(self, state: CircadianState) -> None:
        """The generative peak: seeds, then concepts."""
        GenerateCreativeSeeds(self.context).execute(cycle_id=state.cycle_id)
        BuildCreativeConcepts(self.context).execute(cycle_id=state.cycle_id)
        self.artifacts.write_phase_inputs(cycle_id=state.cycle_id)

    def _digest(self, state: CircadianState) -> None:
        """After a large intake: reduce noise instead of creating immediately."""
        ctx = self.context
        observations = ctx.repositories.observations.list_for_cycle(state.cycle_id)
        texts = [o.statement for o in observations]
        duplicate_rate = ctx.services.novelty.duplicate_rate(texts)
        state.duplicate_rate = duplicate_rate
        ctx.metrics.gauge("duplicate_rate", duplicate_rate)
        ctx.logger.info(
            "phase.digestion",
            observations=len(observations),
            duplicate_rate=duplicate_rate,
            cycle_id=state.cycle_id,
        )

    def _reflect(self, state: CircadianState) -> None:
        """New output meets existing memory: evaluate, compete, judge, develop."""
        ctx = self.context
        concepts = self._competitors(state.cycle_id)
        if not concepts:
            ctx.logger.warning("phase.reflection.empty", cycle_id=state.cycle_id)
            return

        EvaluateConcepts(ctx).execute(concepts)
        self.artifacts.write_concepts(cycle_id=state.cycle_id, concepts=concepts)

        try:
            tournament, finalists = RunCreativeTournament(ctx).execute(
                cycle_id=state.cycle_id, funnel=self.funnel, concepts=concepts
            )
        except EmptyTournamentError as exc:
            ctx.logger.warning("tournament.skipped", reason=str(exc), cycle_id=state.cycle_id)
            return

        self.artifacts.write_tournament(cycle_id=state.cycle_id, tournament=tournament)
        self.artifacts.write_finalists(cycle_id=state.cycle_id, finalists=finalists)
        self.outcome.diversity = tournament.diversity_score

        winner, judgement = JudgeFinalists(ctx).execute(
            cycle_id=state.cycle_id, finalists=finalists
        )
        if winner is None:
            tournament.finish(winner_id="", at=ctx.now(), diversity=tournament.diversity_score)
            ctx.repositories.tournaments.save(tournament)
            ctx.publish(tournament)
            ctx.logger.warning("cycle.no_winner", cycle_id=state.cycle_id)
            return

        DevelopWinner(ctx).execute(winner)
        project = ApproveCreativeProject(ctx).execute(
            winner, judgement=judgement, cycle_id=state.cycle_id
        )
        tournament.finish(
            winner_id=str(winner.id), at=ctx.now(), diversity=tournament.diversity_score
        )
        ctx.repositories.tournaments.save(tournament)
        ctx.publish(tournament)

        self.artifacts.write_tournament(cycle_id=state.cycle_id, tournament=tournament)
        self.artifacts.write_winner(cycle_id=state.cycle_id, concept=winner, project=project)

        self.outcome.winner_title = winner.title
        self.outcome.winner_id = str(winner.id)
        self.outcome.project_id = str(project.id)
        state.recent_quality = winner.total_score.value
        state.recent_novelty = winner.genome.novelty_score.value

    def _second_wind(self, state: CircadianState) -> None:
        """Revisit what the first pass rejected."""
        mutated = MutateRejectedConcepts(self.context).execute(cycle_id=state.cycle_id)
        if mutated:
            EvaluateConcepts(self.context).execute(mutated)

    def _explore(self, state: CircadianState) -> None:
        """Push further from the DNA when novelty is running low."""
        ctx = self.context
        original = ctx.policies.exploration
        ctx.policies.exploration = original.__class__(
            comfort=max(0.0, original.comfort - 0.15),
            edge=original.edge,
            unknown=min(1.0, original.unknown + 0.15),
            unknown_zone_enabled=original.unknown_zone_enabled,
        )
        try:
            GenerateCreativeSeeds(ctx).execute(cycle_id=state.cycle_id)
            new_concepts = BuildCreativeConcepts(ctx).execute(cycle_id=state.cycle_id)
            if new_concepts:
                EvaluateConcepts(ctx).execute(new_concepts)
        finally:
            ctx.policies.exploration = original

    def _consolidate(self, state: CircadianState) -> None:
        """Turn the cycle into memory and, where justified, into learning."""
        ctx = self.context
        ConsolidateMemory(ctx).execute(cycle_id=state.cycle_id)
        AnalyseObsessions(ctx).execute(cycle_id=state.cycle_id)
        meta = RunMetaCognition(ctx).execute(
            cycle_id=state.cycle_id, diversity=self.outcome.diversity
        )
        losers = [
            c.title
            for c in ctx.repositories.concepts.list_for_cycle(state.cycle_id)
            if c.rejection_reasons
        ]
        version = UpdateEvolvingDna(ctx).execute(
            cycle_id=state.cycle_id, winner_title=self.outcome.winner_title, losers=losers
        )
        self.outcome.dna_version = version
        self.artifacts.write_learning(
            cycle_id=state.cycle_id,
            payload={
                "dna_version": version,
                "winner": self.outcome.winner_title,
                "losers": losers,
                "diversity": self.outcome.diversity,
                "meta_cognition": meta.model_dump() if meta else None,
            },
        )
        state.energy = state.energy.spend(EnergyKind.MEMORY_PRESSURE, 60.0)

    def _dream(self, state: CircadianState) -> None:
        """Free association, and occasionally a resurrection."""
        if not self.context.flags.dream_mode_enabled:
            return
        dream = StartDreamCycle(self.context).execute(cycle_id=state.cycle_id)
        self.artifacts.write_dream(cycle_id=state.cycle_id, dream=dream)

    def _deep_sleep(self, state: CircadianState) -> None:
        """No approvals, no research. Compact, verify, prepare the next awakening."""
        ctx = self.context
        counts = self._counts(state.cycle_id)
        self.outcome.counts = counts
        self.outcome.phases = list(state.phases_visited)
        self.artifacts.write_runtime(
            cycle_id=state.cycle_id,
            payload={
                "cycle_id": state.cycle_id,
                "cycle_number": state.cycle_number,
                "phases": list(state.phases_visited),
                "counts": counts,
                "energy": state.energy.as_dict(),
                "random_seed": ctx.random.seed(),
                "flags": ctx.flags.as_dict(),
                "targets": ctx.targets.as_dict(),
                "metrics": ctx.metrics.snapshot(),
                "agent_health": {
                    aid: health.as_dict() for aid, health in ctx.society.health().items()
                },
                "dead_letters": len(ctx.bus.dead_letters()),
                "outcome": self.outcome.as_dict(),
            },
        )
        ctx.logger.info(
            "phase.deep_sleep",
            cycle_id=state.cycle_id,
            winner=self.outcome.winner_title,
            **{k: v for k, v in counts.items()},
        )

    def _competitors(self, cycle_id: str) -> list[CreativeConcept]:
        """Everything eligible to compete in this cycle's tournament.

        SECOND_WIND and EXPLORATION run *after* REFLECTION, so the ideas they
        produce cannot compete in the cycle that made them. They are carried
        forward here instead of being orphaned: a mutation only earns its
        second life if it survives a real tournament later.
        """
        ctx = self.context
        current = [c for c in ctx.repositories.concepts.list_for_cycle(cycle_id) if c.is_alive]
        seen = {str(c.id) for c in current}
        carried = [
            c
            for c in ctx.repositories.concepts.list_by_stage(CreativeStage.CONCEPT, limit=200)
            if c.cycle_id != cycle_id and str(c.id) not in seen
        ]
        if carried:
            ctx.logger.info(
                "tournament.carried_forward", carried=len(carried), cycle_id=cycle_id
            )
        return [*current, *carried]

    # -------------------------------------------------------------- signals

    def _refresh_signals(self, state: CircadianState) -> None:
        """Keep the clock's view of the world current after every phase."""
        ctx = self.context
        cycle_id = state.cycle_id
        state.observation_backlog = len(ctx.repositories.observations.list_for_cycle(cycle_id))
        state.research_backlog = len(ctx.repositories.research.list_for_cycle(cycle_id))
        state.seed_backlog = len(ctx.repositories.seeds.list_for_cycle(cycle_id))
        alive = [c for c in ctx.repositories.concepts.list_for_cycle(cycle_id) if c.is_alive]
        state.concept_backlog = len(alive)
        state.graveyard_size = len(ctx.repositories.concepts.graveyard(limit=500))
        state.unconsolidated_events = len(
            [e for e in ctx.bus.history() if e.cycle_id == cycle_id]
        )
        state.energy = state.energy.restore(
            EnergyKind.MEMORY_PRESSURE, min(20.0, state.unconsolidated_events * 0.6)
        )
        health = ctx.society.health().values()
        calls = sum(h.calls for h in health)
        state.failure_rate = (
            round(sum(h.failures for h in health) / calls, 4) if calls else 0.0
        )
        ctx.metrics.gauge("creative_energy", state.energy.creative.value)
        ctx.metrics.gauge("memory_pressure", state.energy.memory_pressure.value)

    def _counts(self, cycle_id: str) -> dict[str, int]:
        ctx = self.context
        concepts = ctx.repositories.concepts.list_for_cycle(cycle_id)
        return {
            "observations": len(ctx.repositories.observations.list_for_cycle(cycle_id)),
            "research": len(ctx.repositories.research.list_for_cycle(cycle_id)),
            "questions": len(ctx.repositories.questions.list_for_cycle(cycle_id)),
            "seeds": len(ctx.repositories.seeds.list_for_cycle(cycle_id)),
            "concepts": len(concepts),
            "rejected": len([c for c in concepts if c.rejection_reasons]),
            "graveyard": len(ctx.repositories.concepts.graveyard(limit=500)),
            "finalists": len(
                [c for c in concepts if c.stage in {CreativeStage.FINALIST, CreativeStage.APPROVED}]
            ),
            "projects": len(ctx.repositories.projects.list_all(limit=200)),
            "memory_records": ctx.repositories.memory.count(),
        }


__all__ = ["CreativeOrchestrator", "CycleOutcome"]
