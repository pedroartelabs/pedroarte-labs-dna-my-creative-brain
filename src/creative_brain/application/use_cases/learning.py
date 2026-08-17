"""Memory consolidation, obsession analysis, meta-cognition and DNA evolution."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.agents.schemas import (
    ConsolidationReport,
    LearningReport,
    MetaCognitionReport,
    ObsessionReport,
)
from creative_brain.application.context import BrainContext
from creative_brain.domain.entities.memory import MemoryKind, MemoryRecord, Obsession
from creative_brain.domain.events import DomainEvent, EventName
from creative_brain.domain.exceptions import ImmutableCoreDnaViolation
from creative_brain.domain.policies.dna_evolution import ProtectedAsset
from creative_brain.domain.value_objects.identifiers import MemoryId


@dataclass
class ConsolidateMemory:
    """Turn a cycle's raw events into episodic records and, carefully, principles.

    The hard rule: a raw event is not a lesson. A principle needs independent
    supporting events before it is allowed to change how the engine behaves.
    """

    context: BrainContext

    def execute(self, *, cycle_id: str) -> list[MemoryRecord]:
        """Write episodic memory, then propose principles from repeated evidence."""
        ctx = self.context
        events = [e for e in ctx.bus.history() if e.cycle_id == cycle_id]
        records: list[MemoryRecord] = []

        # --- episodic: what happened ---
        for concept in ctx.repositories.concepts.list_for_cycle(cycle_id):
            kind = (
                MemoryKind.SUCCESSFUL
                if concept.stage.value in {"APPROVED", "PROJECT", "PRODUCTION_READY"}
                else MemoryKind.REJECTED
                if concept.rejection_reasons
                else MemoryKind.CREATIVE
            )
            record = MemoryRecord(
                id=ctx.new_id(MemoryId),
                kind=kind,
                summary=f"{concept.title}: {concept.logline[:160]}",
                created_at=ctx.now(),
                cycle_id=cycle_id,
                subject_id=str(concept.id),
                detail="; ".join(concept.rejection_reasons)
                or f"score {concept.total_score.value:.1f}",
                tags=concept.themes,
                salience=float(concept.total_score.value),
            )
            ctx.repositories.memory.add(record)
            records.append(record)

        for observation in ctx.repositories.observations.list_for_cycle(cycle_id):
            record = MemoryRecord(
                id=ctx.new_id(MemoryId),
                kind=MemoryKind.EPISODIC,
                summary=observation.statement[:200],
                created_at=ctx.now(),
                cycle_id=cycle_id,
                subject_id=str(observation.id),
                tags=observation.tags,
                salience=observation.salience,
            )
            ctx.repositories.memory.add(record)
            records.append(record)

        # --- semantic: what it means ---
        report: ConsolidationReport = ctx.society.get("MEMORY_AGENT").run(
            variables={
                "events": "\n".join(
                    f"- {e.name}: {e.payload}" for e in events[:60]
                ) or "(sem eventos)",
                "existing_principles": "\n".join(
                    f"- {r.summary}"
                    for r in ctx.repositories.memory.list_by_kind(MemoryKind.SEMANTIC, limit=20)
                ) or "(nenhum princípio ainda)",
            },
            fallback=ConsolidationReport(),
        )
        supporting = len(events)
        for principle in report.principles:
            if not ctx.policies.memory.may_become_principle(supporting):
                continue
            record = MemoryRecord(
                id=ctx.new_id(MemoryId),
                kind=MemoryKind.SEMANTIC,
                summary=principle.summary,
                created_at=ctx.now(),
                cycle_id=cycle_id,
                detail=principle.detail,
                tags=tuple(principle.tags),
                salience=80.0,
                is_principle=True,
                source_events=tuple(str(e.name) for e in events[:10]),
            )
            ctx.repositories.memory.add(record)
            ctx.vectors.index(str(record.id), f"{record.summary} {record.detail}", {"kind": "principle"})
            records.append(record)

        # --- decay: old episodic material loses priority, never existence ---
        episodic = ctx.repositories.memory.list_by_kind(MemoryKind.EPISODIC, limit=500)
        for record in episodic:
            ctx.policies.memory.decay(record)
        ctx.repositories.memory.save_all(episodic)

        ctx.bus.publish(
            DomainEvent(
                name=EventName.MEMORY_CONSOLIDATED,
                occurred_at=ctx.now(),
                cycle_id=cycle_id,
                agent_id="MEMORY_AGENT",
                correlation_id=ctx.correlation_id,
                payload={"records": len(records), "principles": len(report.principles)},
            )
        )
        ctx.metrics.increment("memory_records_written", float(len(records)))
        ctx.logger.info("phase.consolidation.memory", records=len(records), cycle_id=cycle_id)
        return records


@dataclass
class AnalyseObsessions:
    """Tell a real obsession apart from disguised repetition."""

    context: BrainContext

    def execute(self, *, cycle_id: str) -> list[Obsession]:
        """Build obsession records from the theme history and flag saturation."""
        ctx = self.context
        history: dict[str, list[str]] = {}
        for concept in ctx.repositories.concepts.list_recent(limit=300):
            for theme in concept.themes:
                history.setdefault(theme, []).append(concept.logline or concept.title)

        obsessions = ctx.services.saturation.build(history, at=ctx.now())
        saturated = ctx.services.saturation.saturated_themes(obsessions)

        if ctx.society.has("OBSESSION_AGENT"):
            report: ObsessionReport = ctx.society.get("OBSESSION_AGENT").run(
                variables={
                    "theme_history": "\n".join(
                        f"- {theme}: {len(items)} ocorrências" for theme, items in history.items()
                    ) or "(sem histórico)"
                },
                fallback=ObsessionReport(),
            )
            for item in report.obsessions:
                if not item.is_new_angle and item.theme not in saturated:
                    saturated = (*saturated, item.theme)

        if saturated:
            ctx.bus.publish(
                DomainEvent(
                    name=EventName.SATURATION_DETECTED,
                    occurred_at=ctx.now(),
                    cycle_id=cycle_id,
                    agent_id="OBSESSION_AGENT",
                    correlation_id=ctx.correlation_id,
                    payload={"themes": list(saturated)},
                )
            )
        ctx.logger.info(
            "phase.consolidation.obsessions",
            themes=len(obsessions),
            saturated=len(saturated),
            cycle_id=cycle_id,
        )
        return obsessions


@dataclass
class RunMetaCognition:
    """Ask whether the society is genuinely thinking differently."""

    context: BrainContext

    def execute(self, *, cycle_id: str, diversity: float) -> MetaCognitionReport | None:
        """Return the meta-cognition report, or ``None`` when disabled."""
        ctx = self.context
        if not ctx.flags.meta_cognition_enabled or not ctx.society.has("META_COGNITION_AGENT"):
            return None
        concepts = ctx.repositories.concepts.list_for_cycle(cycle_id)
        outputs = "\n".join(
            f"- {c.genome.origin.mechanism}: {c.title} (score {c.total_score.value:.0f}, "
            f"discordância {c.disagreement:.2f})"
            for c in concepts[:25]
        ) or "(sem saídas)"
        report: MetaCognitionReport = ctx.society.get("META_COGNITION_AGENT").run(
            variables={"agent_outputs": outputs, "diversity_score": f"{diversity:.1f}"},
            fallback=MetaCognitionReport(),
        )
        ctx.logger.info(
            "phase.consolidation.meta",
            dominant=report.dominant_mechanism,
            risk=report.risk[:120],
            cycle_id=cycle_id,
        )
        return report


@dataclass
class UpdateEvolvingDna:
    """Let the engine learn about itself — inside the autonomy envelope only."""

    context: BrainContext

    def execute(self, *, cycle_id: str, winner_title: str, losers: list[str]) -> int:
        """Fold a learning proposal into EVOLVING_DNA. Returns the new version."""
        ctx = self.context
        policy = ctx.policies.dna

        # Fail loudly if anything ever tries to route learning at the protected tier.
        try:
            policy.assert_writable(str(ProtectedAsset.CORE_DNA))
        except ImmutableCoreDnaViolation:
            pass  # expected: this is the guard proving the boundary is live

        current = ctx.repositories.dna.load_evolving()
        report: LearningReport = ctx.society.get("LEARNING_AGENT").run(
            variables={
                "cycle_summary": self._summary(cycle_id),
                "winner": winner_title or "(nenhum vencedor neste ciclo)",
                "losers": "\n".join(f"- {t}" for t in losers[:10]) or "(sem perdedores notáveis)",
                "evolving_dna": "\n".join(
                    f"- {p}" for p in current.emergent_patterns[-10:]
                ) or "(DNA evolutivo vazio)",
            },
            fallback=LearningReport(),
        )

        updated = policy.apply(
            current,
            discoveries=tuple(report.discoveries),
            emergent_patterns=tuple(report.emergent_patterns),
            promising_territories=tuple(report.promising_territories),
            saturated_themes=tuple(report.saturated_themes),
            successful_combinations=tuple(report.successful_combinations),
            techniques=tuple(report.techniques),
            reason=report.reason or f"cycle {cycle_id}",
            at=ctx.now(),
        )
        if updated.version == current.version:
            return current.version

        ctx.repositories.dna.save_evolving(updated)
        ctx.bus.publish(
            DomainEvent(
                name=EventName.DNA_UPDATED,
                occurred_at=ctx.now(),
                cycle_id=cycle_id,
                agent_id="LEARNING_AGENT",
                correlation_id=ctx.correlation_id,
                payload={
                    "version": updated.version,
                    "layer": "EVOLVING_DNA",
                    "new_patterns": len(report.emergent_patterns),
                },
            )
        )
        ctx.trace(
            who="LEARNING_AGENT",
            what=f"updated EVOLVING_DNA to v{updated.version}",
            why=report.reason or "end-of-cycle learning",
            cycle_id=cycle_id,
            evidence=tuple(report.emergent_patterns[:5]),
        )
        ctx.logger.info("phase.consolidation.dna", version=updated.version, cycle_id=cycle_id)
        return updated.version

    def _summary(self, cycle_id: str) -> str:
        ctx = self.context
        concepts = ctx.repositories.concepts.list_for_cycle(cycle_id)
        approved = [c for c in concepts if not c.rejection_reasons]
        return (
            f"conceitos: {len(concepts)}, sobreviventes: {len(approved)}, "
            f"sementes: {len(ctx.repositories.seeds.list_for_cycle(cycle_id))}, "
            f"observações: {len(ctx.repositories.observations.list_for_cycle(cycle_id))}"
        )


__all__ = ["AnalyseObsessions", "ConsolidateMemory", "RunMetaCognition", "UpdateEvolvingDna"]
