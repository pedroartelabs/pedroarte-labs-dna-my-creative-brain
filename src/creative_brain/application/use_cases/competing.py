"""The creative tournament, judgement and project approval."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.agents.schemas import (
    CharacterSet,
    ConsequenceReport,
    Judgement,
    LoreReport,
    ProseArtifact,
    WorldBible,
)
from creative_brain.application.context import BrainContext
from creative_brain.application.use_cases.evaluating import concept_text
from creative_brain.application.use_cases.generating import ProposeTitles
from creative_brain.domain.entities.agent_opinion import DecisionTrace
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.project import CreativeProject
from creative_brain.domain.entities.tournament import CreativeTournament, TournamentFunnel
from creative_brain.domain.exceptions import EmptyTournamentError
from creative_brain.domain.policies.lifecycle import ADVANCING_ORDER, CreativeStage
from creative_brain.domain.value_objects.identifiers import ProjectId, TournamentId


@dataclass
class RunCreativeTournament:
    """Run the elimination funnel over this cycle's concepts."""

    context: BrainContext

    def execute(
        self, *, cycle_id: str, funnel: TournamentFunnel, concepts: list[CreativeConcept]
    ) -> tuple[CreativeTournament, list[CreativeConcept]]:
        """Return the tournament record and the surviving finalists."""
        ctx = self.context
        alive = [c for c in concepts if c.is_alive]
        if not alive:
            raise EmptyTournamentError(f"cycle {cycle_id} produced no concepts to compete")

        tournament = CreativeTournament.start(
            tournament_id=ctx.new_id(TournamentId),
            cycle_id=cycle_id,
            funnel=funnel,
            entrants=tuple(str(c.id) for c in alive),
            at=ctx.now(),
        )

        current = alive
        for step in funnel.steps:
            outcome = ctx.services.tournament.select(current, step.survivors)
            tournament.record_round(
                stage=step.stage,
                entrants=tuple(str(c.id) for c in current),
                survivors=tuple(str(c.id) for c in outcome.survivors),
                at=ctx.now(),
            )
            for loser in outcome.eliminated:
                reason = outcome.reasons.get(str(loser.id), "eliminated in the funnel")
                self._eliminate(loser, reason, cycle_id)
            for survivor in outcome.survivors:
                self._promote(survivor, step.stage, cycle_id)
            current = list(outcome.survivors)

        tournament.diversity_score = ctx.services.tournament.batch_diversity(alive)
        ctx.repositories.tournaments.save(tournament)
        ctx.publish(tournament)
        ctx.metrics.observe("tournament_entrants", float(len(alive)))
        ctx.metrics.gauge("diversity_score", tournament.diversity_score)
        ctx.logger.info(
            "tournament.finished_rounds",
            entrants=len(alive),
            finalists=len(current),
            diversity=tournament.diversity_score,
            cycle_id=cycle_id,
        )
        return tournament, current

    def _promote(self, concept: CreativeConcept, stage: CreativeStage, cycle_id: str) -> None:
        """Walk a survivor forward to the round's stage, one legal step at a time."""
        ctx = self.context
        target_index = ADVANCING_ORDER.index(stage)
        while ADVANCING_ORDER.index(concept.stage) < target_index:
            nxt = ADVANCING_ORDER[ADVANCING_ORDER.index(concept.stage) + 1]
            concept.advance_to(nxt, at=ctx.now(), reason=f"survived the {stage} round")
        ctx.repositories.concepts.save(concept)
        ctx.publish(concept)

    def _eliminate(self, concept: CreativeConcept, reason: str, cycle_id: str) -> None:
        """Reject a loser and route it to the mutation pool or the graveyard."""
        ctx = self.context
        concept.reject((reason,), at=ctx.now(), by="CREATIVE_TOURNAMENT")
        if ctx.flags.mutation_enabled and ctx.policies.mutation.is_mutable(concept):
            concept.send_to_mutation_pool(at=ctx.now())
        else:
            concept.entomb(at=ctx.now())
        ctx.repositories.concepts.save(concept)
        ctx.publish(concept)
        ctx.metrics.increment("ideas_rejected_total")


@dataclass
class JudgeFinalists:
    """CREATIVE_JUDGE_AGENT picks a winner — or rejects the whole round."""

    context: BrainContext

    def execute(
        self, *, cycle_id: str, finalists: list[CreativeConcept]
    ) -> tuple[CreativeConcept | None, Judgement | None]:
        """Return the approved winner, or ``(None, judgement)`` when nothing passes."""
        ctx = self.context
        if not finalists:
            return None, None
        judge = ctx.society.get("CREATIVE_JUDGE_AGENT")

        ranked = sorted(finalists, key=lambda c: c.total_score.value, reverse=True)
        for candidate in ranked:
            violations = ctx.policies.constitution.violations(candidate)
            if violations:
                self._reject(candidate, violations, cycle_id, "constitution")
                continue

            judgement: Judgement = judge.run(
                variables={
                    "subject": concept_text(candidate),
                    "evidence": "\n".join(
                        f"- {o.agent} [{o.verdict}] {o.rationale[:180]}"
                        for o in candidate.opinions
                    )
                    or "(sem evidências)",
                    "scores": ", ".join(
                        f"{k}={v:.1f}" for k, v in candidate.scoreboard.as_dict().items()
                    ),
                },
                hints={"subject": concept_text(candidate)},
                fallback=Judgement(decision="REJECT", rationale="judge unavailable"),
            )
            if not judgement.approves:
                self._reject(
                    candidate,
                    (judgement.rationale or "judge rejected without a stated reason",),
                    cycle_id,
                    "CREATIVE_JUDGE_AGENT",
                )
                continue

            candidate.advance_to(
                CreativeStage.APPROVED, at=ctx.now(), reason=judgement.rationale[:200]
            )
            ctx.repositories.concepts.save(candidate)
            ctx.publish(candidate)
            ctx.metrics.increment("ideas_approved_total")
            ctx.trace(
                who="CREATIVE_JUDGE_AGENT",
                what=f"approved '{candidate.title}'",
                why=judgement.rationale,
                cycle_id=cycle_id,
                inputs=tuple(str(c.id) for c in ranked),
                scores=candidate.scoreboard.as_dict(),
                evidence=tuple(judgement.evidence),
            )
            return candidate, judgement

        ctx.logger.warning("judge.rejected_all", finalists=len(finalists), cycle_id=cycle_id)
        return None, None

    def _reject(
        self, concept: CreativeConcept, reasons: tuple[str, ...], cycle_id: str, by: str
    ) -> None:
        ctx = self.context
        concept.reject(reasons, at=ctx.now(), by=by)
        if ctx.flags.mutation_enabled and ctx.policies.mutation.is_mutable(concept):
            concept.send_to_mutation_pool(at=ctx.now())
        else:
            concept.entomb(at=ctx.now())
        ctx.repositories.concepts.save(concept)
        ctx.publish(concept)
        ctx.metrics.increment("ideas_rejected_total")
        ctx.trace(
            who=by,
            what=f"rejected '{concept.title}'",
            why="; ".join(reasons),
            cycle_id=cycle_id,
            inputs=(str(concept.id),),
            scores=concept.scoreboard.as_dict(),
        )


@dataclass
class DevelopWinner:
    """Build out the winner: title, world, characters, consequences, pitch, synopsis."""

    context: BrainContext

    def execute(self, concept: CreativeConcept) -> CreativeConcept:
        """Attach every prose artifact a production engine will need."""
        ctx = self.context
        ProposeTitles(ctx).execute(concept)

        world: WorldBible = ctx.society.get("WORLD_ARCHITECT_AGENT").run(
            variables={"concept": concept_text(concept)},
            hints={"subject": concept_text(concept)},
            fallback=WorldBible(),
        )
        concept.attach("world_bible", _render_world(world))

        characters: CharacterSet = ctx.society.get("CHARACTER_ARCHITECT_AGENT").run(
            variables={
                "concept": concept_text(concept),
                "world": concept.artifacts.get("world_bible", ""),
            },
            fallback=CharacterSet(),
        )
        concept.attach("characters", _render_characters(characters))

        consequences: ConsequenceReport = ctx.society.get("EXTREME_CONSEQUENCE_AGENT").run(
            variables={"premise": concept.artifacts.get("premise", concept.logline)},
            fallback=ConsequenceReport(),
        )
        premise = concept.artifacts.get("premise", concept.logline)
        concept.attach("premise", f"{premise}\n\n{_render_consequences(consequences)}")

        for key, agent_id in (("pitch", "PITCH_BUILDER"), ("synopsis", "SYNOPSIS_BUILDER")):
            prose: ProseArtifact = ctx.society.get(agent_id).run(
                variables={"subject": concept_text(concept)},
                hints={"title": concept.title, "logline": concept.logline},
                fallback=ProseArtifact(text=""),
            )
            concept.attach(key, prose.text)

        if ctx.flags.lore_connections_enabled and ctx.society.has("LORE_CONNECTION_AGENT"):
            lore: LoreReport = ctx.society.get("LORE_CONNECTION_AGENT").run(
                variables={
                    "subject": concept_text(concept),
                    "canon": "\n".join(ctx.repositories.projects.canon().values()) or "(vazio)",
                },
                fallback=LoreReport(),
            )
            if lore.connections and not lore.force_shared_universe:
                for connection in lore.connections:
                    ctx.graph.add_edge(str(concept.id), "canon", connection.kind.lower())

        ctx.repositories.concepts.save(concept)
        return concept


@dataclass
class ApproveCreativeProject:
    """Promote an approved concept into a project and a production manifest."""

    context: BrainContext

    def execute(
        self, concept: CreativeConcept, *, judgement: Judgement | None, cycle_id: str
    ) -> CreativeProject:
        """Create the project, mark it production-ready and persist everything."""
        from creative_brain.adapters.production import suggest_engines

        ctx = self.context
        concept.advance_to(CreativeStage.PROJECT, at=ctx.now(), reason="approved by the judge")

        project = CreativeProject(
            id=ctx.new_id(ProjectId),
            concept_id=str(concept.id),
            title=concept.title,
            logline=concept.logline,
            central_question=concept.central_question,
            genome=concept.genome,
            created_at=ctx.now(),
            cycle_id=cycle_id,
            scoreboard=concept.scoreboard,
            total_score=concept.total_score.value,
            artifacts=dict(concept.artifacts),
        )
        if judgement is not None:
            project.add_trace(
                DecisionTrace(
                    who="CREATIVE_JUDGE_AGENT",
                    what="selected this project as the winner of the cycle",
                    why=judgement.rationale,
                    decided_at=ctx.now(),
                    inputs=(str(concept.id),),
                    scores=concept.scoreboard.as_dict(),
                    evidence=tuple(judgement.evidence),
                    cycle_id=cycle_id,
                    correlation_id=ctx.correlation_id,
                )
            )

        engines = suggest_engines(project.execution_manifest())
        project.mark_production_ready(at=ctx.now(), engines=engines)
        concept.advance_to(
            CreativeStage.PRODUCTION_READY, at=ctx.now(), reason="manifest generated"
        )

        ctx.repositories.projects.save(project)
        ctx.repositories.concepts.save(concept)
        ctx.publish(project)
        ctx.publish(concept)
        ctx.vectors.index(
            str(project.id), concept_text(concept), {"kind": "canon", "title": project.title}
        )

        if ctx.flags.production_handoff_enabled:
            manifest = project.execution_manifest()
            for adapter in ctx.production:
                if adapter.accepts(manifest):
                    receipt = adapter.hand_off(manifest)
                    ctx.logger.info("production.handoff", engine=adapter.engine, receipt=receipt)

        ctx.logger.info(
            "project.production_ready",
            project_id=str(project.id),
            title=project.title,
            engines=list(engines),
        )
        return project


def _render_world(world: WorldBible) -> str:
    """Turn the structured world bible into readable markdown."""
    sections = [
        ("Regras", "\n".join(f"- {r}" for r in world.rules)),
        ("Economia", world.economy),
        ("Instituições", world.institutions),
        ("Tecnologia", world.technology),
        ("Cultura", world.culture),
        ("Linguagem", world.language),
        ("Classes", "\n".join(f"- {c}" for c in world.classes)),
        ("Tabus", "\n".join(f"- {t}" for t in world.taboos)),
        ("Poder", world.power),
    ]
    return "\n\n".join(f"## {title}\n{body}" for title, body in sections if body)


def _render_characters(characters: CharacterSet) -> str:
    """Turn character sheets into readable markdown."""
    return "\n\n".join(
        f"## {c.name}\n"
        f"- Posição diante do sistema: {c.position}\n"
        f"- Quer: {c.want}\n"
        f"- Teme: {c.fear}\n"
        f"- Contradição: {c.contradiction}"
        for c in characters.characters
    )


def _render_consequences(report: ConsequenceReport) -> str:
    """Turn the consequence timeline into readable markdown."""
    if not report.horizons:
        return ""
    lines = "\n".join(f"- **{h.horizon}**: {h.effect}" for h in report.horizons)
    risk = f"\n\nRisco sistêmico: {report.systemic_risk}" if report.systemic_risk else ""
    return f"### Consequências\n{lines}{risk}"


__all__ = [
    "ApproveCreativeProject",
    "DevelopWinner",
    "JudgeFinalists",
    "RunCreativeTournament",
]
