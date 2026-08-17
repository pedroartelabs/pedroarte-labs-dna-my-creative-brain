"""Use cases for the CREATION, SECOND_WIND and EXPLORATION phases."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.agents.schemas import ConceptDraft, SeedBatch, TitleBatch
from creative_brain.application.context import BrainContext
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.question import CreativeSeed
from creative_brain.domain.events import DomainEvent, EventName
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.creative_distance import CreativeDistance, CreativeZone
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId, SeedId

#: Which cognitive mechanism each generator agent represents.
GENERATOR_MECHANISM: dict[str, OriginMechanism] = {
    "WHAT_IF_AGENT": OriginMechanism.WHAT_IF,
    "CONCEPT_COLLIDER_AGENT": OriginMechanism.COLLISION,
    "INVERSION_AGENT": OriginMechanism.INVERSION,
    "PARADOX_AGENT": OriginMechanism.PARADOX,
    "THE_UNKNOWN_AGENT": OriginMechanism.UNKNOWN_ZONE,
}


@dataclass
class GenerateCreativeSeeds:
    """Fire every divergent generator and collect the seeds they produce.

    Over-production is the point: the tournament exists to kill most of this.
    """

    context: BrainContext

    def execute(self, *, cycle_id: str, zone_bias: CreativeZone | None = None) -> list[CreativeSeed]:
        """Run all enabled generators once each."""
        ctx = self.context
        questions = ctx.repositories.questions.list_for_cycle(cycle_id)
        findings = ctx.repositories.research.list_for_cycle(cycle_id)
        observations = ctx.repositories.observations.list_for_cycle(cycle_id)

        source_material = "\n".join(
            [
                *(f"- pergunta: {q.text}" for q in questions[:6]),
                *(f"- pesquisa: {f.summary}" for f in findings[:3]),
                *(f"- observação: {o.statement}" for o in observations[:6]),
            ]
        ) or "(sem material acumulado neste ciclo)"

        evolving = ctx.repositories.dna.load_evolving()
        history = ctx.repositories.concepts.corpus(limit=25)

        seeds: list[CreativeSeed] = []
        for agent in ctx.society.generators():
            if agent.id == "THE_UNKNOWN_AGENT" and not ctx.flags.unknown_zone_enabled:
                continue
            mechanism = GENERATOR_MECHANISM.get(agent.id, OriginMechanism.OBSERVATION)
            batch: SeedBatch = agent.run(
                variables={
                    "source": source_material,
                    "subject": source_material,
                    "concepts": source_material,
                    "history": "\n".join(f"- {text}" for text in list(history.values())[:15])
                    or "(memória vazia)",
                    "saturated_themes": ", ".join(evolving.saturated_themes) or "(nenhum)",
                    "count": str(ctx.targets.seeds_per_generator),
                    "depth": "2",
                },
                hints={"count": str(ctx.targets.seeds_per_generator)},
                fallback=SeedBatch(),
            )
            for item in batch.all_items():
                if not item.statement.strip():
                    continue
                question = questions[len(seeds) % len(questions)] if questions else None
                seed = CreativeSeed(
                    id=ctx.new_id(SeedId),
                    statement=item.statement,
                    created_at=ctx.now(),
                    origin=GenomeOrigin(
                        mechanism=mechanism,
                        observation=observations[0].statement if observations else None,
                        inversion=item.axis or None,
                        paradox=item.paradox or None,
                        collision=tuple(item.ingredients),
                        research=findings[0].summary if findings else None,
                    ),
                    cycle_id=cycle_id,
                    question_id=str(question.id) if question else "",
                    observation_id=str(observations[0].id) if observations else "",
                    tags=tuple(item.themes),
                    heat=float(item.heat),
                )
                ctx.repositories.seeds.add(seed)
                ctx.bus.publish(
                    DomainEvent(
                        name=EventName.SEED_CREATED,
                        occurred_at=seed.created_at,
                        cycle_id=cycle_id,
                        subject_id=str(seed.id),
                        agent_id=agent.id,
                        correlation_id=ctx.correlation_id,
                        payload={"mechanism": str(mechanism), "heat": seed.heat},
                    )
                )
                seeds.append(seed)

        ctx.metrics.increment("seeds_generated", float(len(seeds)))
        ctx.logger.info(
            "phase.creation.seeds",
            seeds=len(seeds),
            generators=len(ctx.society.generators()),
            cycle_id=cycle_id,
            zone_bias=str(zone_bias) if zone_bias else "",
        )
        return seeds


@dataclass
class BuildCreativeConcepts:
    """Turn the hottest seeds into structured concepts, spread across the three zones."""

    context: BrainContext

    def execute(self, *, cycle_id: str) -> list[CreativeConcept]:
        """Build concepts from seeds, honouring the exploration allocation."""
        ctx = self.context
        seeds = sorted(
            ctx.repositories.seeds.list_for_cycle(cycle_id), key=lambda s: s.heat, reverse=True
        )
        if not seeds:
            return []

        allocation = ctx.policies.exploration.allocate(min(ctx.targets.concepts, len(seeds)))
        core = ctx.repositories.dna.load_core()
        dna_text = "\n".join(f"- {line}" for line in core.vocabulary()[:12])

        builder = ctx.society.get("CONCEPT_BUILDER")
        concepts: list[CreativeConcept] = []
        seed_iter = iter(seeds)

        for zone, slots in allocation.items():
            for _ in range(slots):
                seed = next(seed_iter, None)
                if seed is None:
                    break
                draft: ConceptDraft = builder.run(
                    variables={
                        "seed": seed.statement,
                        "question": seed.question_id or "(sem pergunta associada)",
                        "dna": dna_text,
                        "zone": str(zone),
                    },
                    hints={"seed": seed.statement, "zone": str(zone)},
                    fallback=ConceptDraft(title="", logline=""),
                )
                if not draft.title.strip():
                    continue
                concept = CreativeConcept.germinate(
                    concept_id=ctx.new_id(ConceptId),
                    title=draft.title,
                    logline=draft.logline,
                    origin=seed.origin,
                    at=ctx.now(),
                    cycle_id=cycle_id,
                    seed_id=str(seed.id),
                    question_id=seed.question_id,
                    themes=tuple(draft.themes) or seed.tags,
                    tone=tuple(draft.tone),
                    structure=tuple(draft.structure),
                )
                concept.attach("concept", draft.logline)
                if draft.premise:
                    concept.attach("premise", draft.premise)
                if draft.central_question:
                    concept.attach("central_question", draft.central_question)
                # The concept starts at the distance its zone asked for;
                # CalculateCreativeDistance reconciles it against measurement.
                concept.apply_evaluation(
                    distance=CreativeDistance.clamped(
                        ctx.policies.exploration.target_distance(zone)
                    )
                )
                concept.advance_to(
                    CreativeStage.CONCEPT,
                    at=ctx.now(),
                    reason=f"seed promoted into the {zone} zone",
                )
                ctx.repositories.concepts.save(concept)
                ctx.vectors.index(
                    str(concept.id),
                    f"{concept.title} {concept.logline} {concept.central_question}",
                    {"kind": "concept", "cycle_id": cycle_id},
                )
                ctx.graph.add_node(
                    str(concept.id), "Concept", {"title": concept.title, "cycle_id": cycle_id}
                )
                ctx.graph.add_edge(str(concept.id), str(seed.id), "derived_from")
                ctx.publish(concept)
                concepts.append(concept)

        ctx.metrics.increment("concepts_built", float(len(concepts)))
        ctx.logger.info("phase.creation.concepts", concepts=len(concepts), cycle_id=cycle_id)
        return concepts


@dataclass
class ProposeTitles:
    """Ask TITLE_AGENT for stronger titles and adopt the best one."""

    context: BrainContext

    def execute(self, concept: CreativeConcept) -> str:
        """Return the adopted title (possibly the original)."""
        ctx = self.context
        if not ctx.society.has("TITLE_AGENT"):
            return concept.title
        agent = ctx.society.get("TITLE_AGENT")
        batch: TitleBatch = agent.run(
            variables={
                "concept": f"{concept.title} — {concept.logline}\n{concept.artifacts.get('premise', '')}",
                "count": str(ctx.targets.titles),
            },
            hints={"count": str(ctx.targets.titles)},
            fallback=TitleBatch(),
        )
        best = next((t for t in batch.titles if t.title.strip() and t.double_meaning), None)
        if best is None:
            return concept.title
        concept.title = best.title.strip()
        return concept.title


__all__ = ["GENERATOR_MECHANISM", "BuildCreativeConcepts", "GenerateCreativeSeeds", "ProposeTitles"]
