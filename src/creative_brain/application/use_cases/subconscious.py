"""Mutation, dreaming and resurrection — the parts of the mind that work at night."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.agents.schemas import DreamReport, MutationResult
from creative_brain.application.context import BrainContext
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import Dream
from creative_brain.domain.entities.question import CreativeSeed
from creative_brain.domain.events import DomainEvent, EventName
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.policies.mutation import MutationOperator
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId, DreamId, SeedId


@dataclass
class MutateRejectedConcepts:
    """Give the most promising dead ideas a structurally different second life."""

    context: BrainContext

    def execute(self, *, cycle_id: str) -> list[CreativeConcept]:
        """Mutate up to ``targets.mutations`` concepts from the mutation pool."""
        ctx = self.context
        if not ctx.flags.mutation_enabled:
            return []

        pool = ctx.repositories.concepts.list_by_stage(CreativeStage.MUTATION_POOL, limit=100)
        candidates = ctx.policies.mutation.rank(pool)[: ctx.targets.mutations]
        if not candidates:
            return []

        agent = ctx.society.get("MUTATION_AGENT")
        operators = list(MutationOperator)
        mutated: list[CreativeConcept] = []

        for parent in candidates:
            operator = ctx.random.pick(operators)
            result: MutationResult = agent.run(
                variables={
                    "original": (
                        f"{parent.title} — {parent.logline}\n"
                        f"{parent.artifacts.get('premise', '')}\n"
                        f"Rejeitada por: {'; '.join(parent.rejection_reasons)}"
                    ),
                    "operator": str(operator),
                    "instruction": ctx.policies.mutation.instruction_for(operator),
                },
                hints={"operator": str(operator), "title": parent.title},
                fallback=MutationResult(title=""),
            )
            if not result.title.strip():
                continue

            child = CreativeConcept.germinate(
                concept_id=ctx.new_id(ConceptId),
                title=result.title,
                logline=result.logline or parent.logline,
                origin=GenomeOrigin(
                    mechanism=OriginMechanism.MUTATION,
                    observation=parent.genome.origin.observation,
                    inversion=parent.genome.origin.inversion,
                    paradox=parent.genome.origin.paradox,
                    collision=parent.genome.origin.collision,
                ),
                at=ctx.now(),
                cycle_id=cycle_id,
                seed_id=parent.seed_id,
                question_id=parent.question_id,
                themes=tuple(result.themes) or parent.themes,
                lineage=parent.lineage,
            )
            child.record_mutation(at=ctx.now(), operator=str(operator), parent_id=str(parent.id))
            if result.premise:
                child.attach("premise", result.premise)
            if result.central_question:
                child.attach("central_question", result.central_question)
            child.advance_to(
                CreativeStage.CONCEPT, at=ctx.now(), reason=f"mutation via {operator}"
            )

            parent.entomb(at=ctx.now())
            ctx.repositories.concepts.save(parent)
            ctx.repositories.concepts.save(child)
            ctx.graph.add_edge(str(child.id), str(parent.id), "mutated_from")
            ctx.publish(parent)
            ctx.publish(child)
            ctx.metrics.increment("mutations_created")
            mutated.append(child)

        ctx.logger.info("phase.second_wind.mutations", mutated=len(mutated), cycle_id=cycle_id)
        return mutated


@dataclass
class StartDreamCycle:
    """DREAM_MODE: free association with plausibility, market and genre switched off."""

    context: BrainContext

    def execute(self, *, cycle_id: str) -> Dream:
        """Dream, harvest usable fragments as seeds, and possibly resurrect the dead."""
        ctx = self.context
        dream = Dream(id=ctx.new_id(DreamId), started_at=ctx.now(), cycle_id=cycle_id)
        ctx.bus.publish(
            DomainEvent(
                name=EventName.DREAM_STARTED,
                occurred_at=dream.started_at,
                cycle_id=cycle_id,
                subject_id=str(dream.id),
                agent_id="DREAM_AGENT",
                correlation_id=ctx.correlation_id,
            )
        )

        graveyard = ctx.repositories.concepts.graveyard(limit=40)
        material = "\n".join(
            [
                *(f"- {c.title}: {c.logline}" for c in graveyard[:8]),
                *(
                    f"- {o.statement}"
                    for o in ctx.repositories.observations.list_for_cycle(cycle_id)[:5]
                ),
            ]
        ) or "(nada além do silêncio deste ciclo)"

        report: DreamReport = ctx.society.get("DREAM_AGENT").run(
            variables={"material": material, "count": str(ctx.targets.dream_fragments)},
            hints={"count": str(ctx.targets.dream_fragments)},
            fallback=DreamReport(),
        )
        for fragment in report.fragments:
            dream.add_fragment(fragment)

        harvested = self._harvest(dream, cycle_id)
        resurrected = self._resurrect(graveyard, cycle_id)
        dream.resurrected_ids = tuple(str(c.id) for c in resurrected)
        dream.notes = report.notes
        dream.finish(at=ctx.now(), harvested=harvested, strangeness=report.strangeness)

        ctx.repositories.dreams.add(dream)
        ctx.bus.publish(
            DomainEvent(
                name=EventName.DREAM_FINISHED,
                occurred_at=dream.finished_at,
                cycle_id=cycle_id,
                subject_id=str(dream.id),
                agent_id="DREAM_AGENT",
                correlation_id=ctx.correlation_id,
                payload={
                    "fragments": len(dream.fragments),
                    "harvested": len(harvested),
                    "resurrected": len(resurrected),
                    "strangeness": dream.strangeness,
                },
            )
        )
        ctx.logger.info(
            "phase.dreaming",
            fragments=len(dream.fragments),
            harvested=len(harvested),
            resurrected=len(resurrected),
            cycle_id=cycle_id,
        )
        return dream

    def _harvest(self, dream: Dream, cycle_id: str) -> tuple[str, ...]:
        """Turn dream fragments into seeds the next cycle can work with."""
        ctx = self.context
        harvested: list[str] = []
        for fragment in dream.fragments:
            seed = CreativeSeed(
                id=ctx.new_id(SeedId),
                statement=fragment,
                created_at=ctx.now(),
                origin=GenomeOrigin(mechanism=OriginMechanism.DREAM, dream=str(dream.id)),
                cycle_id=cycle_id,
                tags=("dream",),
                heat=float(dream.strangeness),
            )
            ctx.repositories.seeds.add(seed)
            harvested.append(str(seed.id))
        return tuple(harvested)

    def _resurrect(self, graveyard: list[CreativeConcept], cycle_id: str) -> list[CreativeConcept]:
        """Occasionally pull a buried idea back into the mutation pool.

        The original stays buried: resurrection copies it into a new lineage so
        the record of why it died is never lost.
        """
        ctx = self.context
        candidates = [c for c in graveyard if c.mutation_potential >= 55.0]
        if not candidates:
            return []
        revived: list[CreativeConcept] = []
        for source in ctx.random.sample(candidates, min(2, len(candidates))):
            if not ctx.random.chance(0.5):
                continue
            copy = source.resurrect_as(
                concept_id=ctx.new_id(ConceptId),
                at=ctx.now(),
                note="ressuscitada durante o DREAM_MODE",
                cycle_id=cycle_id,
            )
            ctx.repositories.concepts.save(copy)
            ctx.graph.add_edge(str(copy.id), str(source.id), "resurrected_from")
            ctx.publish(copy)
            ctx.metrics.increment("ideas_resurrected")
            revived.append(copy)
        return revived


__all__ = ["MutateRejectedConcepts", "StartDreamCycle"]
