"""Evaluation use cases: novelty, creative distance, and the critic society."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.agents.schemas import Critique
from creative_brain.application.context import BrainContext
from creative_brain.domain.entities.agent_opinion import AgentOpinion, Verdict
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.services.evaluation import NoveltyAssessment
from creative_brain.domain.value_objects.creative_distance import CreativeDistance
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard, ScoreCriterion

#: Which prompt variable each critic expects beyond the shared ``subject``.
CRITIC_EXTRA_VARIABLES: dict[str, tuple[str, ...]] = {
    "PEDRO_DNA_AGENT": ("core_dna",),
    "ANTI_CLICHE_AGENT": ("known_patterns",),
    "NOVELTY_AGENT": ("nearest_matches",),
    "BLUE_TEAM_AGENT": ("attacks",),
    "LORE_CONNECTION_AGENT": ("canon",),
}

KNOWN_PATTERNS = (
    "distopia de vigilância com resistência clandestina",
    "IA que ganha consciência e ameaça a humanidade",
    "escolhido que descobre ser especial",
    "apocalipse seguido de comunidade de sobreviventes",
    "sistema de castas com prova de aptidão na adolescência",
    "viagem no tempo com paradoxo do avô",
)


def concept_text(concept: CreativeConcept) -> str:
    """The searchable representation of a concept used everywhere it is compared."""
    return " ".join(
        part
        for part in (
            concept.title,
            concept.logline,
            concept.central_question,
            concept.artifacts.get("premise", ""),
            " ".join(concept.themes),
        )
        if part
    )


@dataclass
class EvaluateNovelty:
    """Measure how new a concept is against memory, canon and the graveyard."""

    context: BrainContext

    def execute(self, concept: CreativeConcept, *, exclude_self: bool = True) -> NoveltyAssessment:
        """Score novelty and record the nearest internal match as evidence."""
        ctx = self.context
        corpus = ctx.repositories.concepts.corpus(limit=300)
        if exclude_self:
            corpus.pop(str(concept.id), None)
        corpus.update(ctx.repositories.projects.canon())

        assessment = ctx.services.novelty.assess(concept_text(concept), corpus)
        concept.apply_evaluation(novelty=assessment.novelty)
        ctx.metrics.observe("average_novelty_score", assessment.novelty.value)
        if assessment.is_duplicate:
            ctx.metrics.increment("duplicates_detected")
        return assessment


@dataclass
class CalculateCreativeDistance:
    """Reconcile the zone a concept was *asked* to occupy with where it actually landed.

    The exploration policy assigns every concept a target zone before it is
    written, and the generator is told to aim for it. Lexical distance alone is
    a weak proxy — a fresh idea shares little vocabulary with the DNA whether it
    is genuinely new or merely oddly worded — so the intent carries most of the
    weight and the measurement corrects it. An idea meant for the comfort zone
    that measures wildly alien gets pulled outward, and vice versa.
    """

    context: BrainContext

    def execute(self, concept: CreativeConcept) -> None:
        """Fold the reconciled distance into the concept's genome."""
        ctx = self.context
        weight = min(1.0, max(0.0, ctx.distance_measurement_weight))
        core = ctx.repositories.dna.load_core()
        evolving = ctx.repositories.dna.load_evolving()
        vocabulary = (*core.vocabulary(), *evolving.emergent_patterns)

        measured = ctx.services.distance.measure_against_canon(
            concept_text(concept), vocabulary, ctx.repositories.projects.canon()
        )
        intended = concept.genome.creative_distance
        reconciled = CreativeDistance.clamped(
            intended.value * (1.0 - weight) + measured.value * weight
        )

        concept.apply_evaluation(distance=reconciled)
        ctx.metrics.observe("average_creative_distance", reconciled.value)
        ctx.metrics.observe("measured_creative_distance", measured.value)


@dataclass
class RunCriticSociety:
    """Ask every critic for a structured opinion on one concept.

    RED_TEAM runs before BLUE_TEAM so the defence answers real attacks rather
    than arguing with itself.
    """

    context: BrainContext

    def execute(self, concept: CreativeConcept) -> list[AgentOpinion]:
        """Collect opinions and fold them into the concept's scoreboard."""
        ctx = self.context
        subject = self._subject(concept)
        core = ctx.repositories.dna.load_core()
        novelty_hits = ctx.vectors.query(concept_text(concept), top_k=3)
        nearest = "\n".join(
            f"- {hit.key}: {hit.text[:160]} (similaridade {hit.score:.2f})"
            for hit in novelty_hits
            if hit.key != str(concept.id)
        ) or "(nenhuma correspondência próxima)"

        attacks = "(ainda sem ataques registrados)"
        opinions: list[AgentOpinion] = []

        for agent in ctx.society.critics():
            variables = {
                "subject": subject,
                "core_dna": "\n".join(f"- {v}" for v in core.vocabulary()[:12]),
                "known_patterns": "\n".join(f"- {p}" for p in KNOWN_PATTERNS),
                "nearest_matches": nearest,
                "attacks": attacks,
                "canon": "\n".join(f"- {t}" for t in ctx.repositories.projects.canon().values())
                or "(cânone vazio)",
            }
            critique: Critique = agent.run(
                variables=variables,
                hints={"subject": subject},
                fallback=Critique(rationale=f"{agent.id} indisponível", confidence=0.0),
            )
            opinion = AgentOpinion(
                agent=agent.id,
                verdict=_verdict(critique.verdict),
                rationale=critique.rationale,
                created_at=ctx.now(),
                scores=ScoreBoard.from_mapping(critique.scores),
                evidence=tuple(critique.evidence),
                confidence=float(critique.confidence),
            )
            concept.add_opinion(opinion)
            opinions.append(opinion)
            if agent.id == "RED_TEAM_AGENT" and critique.evidence:
                attacks = "\n".join(f"- {item}" for item in critique.evidence)

        self._fill_missing_criteria(concept)
        concept.apply_total(ctx.policies.scoring.total_for(concept), at=ctx.now())
        ctx.metrics.observe("agent_disagreement_rate", concept.disagreement)
        return opinions

    def _subject(self, concept: CreativeConcept) -> str:
        return (
            f"Título: {concept.title}\n"
            f"Logline: {concept.logline}\n"
            f"Pergunta central: {concept.central_question or '(não formulada)'}\n"
            f"Premissa: {concept.artifacts.get('premise', '(não escrita)')}\n"
            f"Temas: {', '.join(concept.themes) or '(sem temas)'}\n"
            f"Mecanismo de origem: {concept.genome.origin.mechanism}"
        )

    def _fill_missing_criteria(self, concept: CreativeConcept) -> None:
        """Give unscored criteria a neutral value derived from what *was* measured.

        Without this a criterion nobody happened to score would silently count
        as zero and distort the weighted total.
        """
        measured = concept.scoreboard.scores
        if not measured:
            return
        neutral = sum(s.value for s in measured.values()) / len(measured)
        filled = dict(measured)
        for criterion in ScoreCriterion:
            filled.setdefault(criterion, CreativeScore.clamped(neutral))
        # Genome-level measurements are authoritative where they exist.
        filled[ScoreCriterion.ORIGINALITY] = CreativeScore.clamped(
            (filled[ScoreCriterion.ORIGINALITY].value + concept.genome.novelty_score.value) / 2
        )
        concept.scoreboard = ScoreBoard(filled)


@dataclass
class EvaluateConcepts:
    """The full evaluation pass over a batch of concepts."""

    context: BrainContext

    def execute(self, concepts: list[CreativeConcept]) -> list[CreativeConcept]:
        """Measure, criticise and score every concept, then persist them."""
        ctx = self.context
        novelty = EvaluateNovelty(ctx)
        distance = CalculateCreativeDistance(ctx)
        critics = RunCriticSociety(ctx)

        for concept in concepts:
            novelty.execute(concept)
            distance.execute(concept)
            critics.execute(concept)
            concept.mutation_potential = self._mutation_potential(concept)
            ctx.repositories.concepts.save(concept)
            ctx.trace(
                who="CRITIC_SOCIETY",
                what=f"evaluated '{concept.title}'",
                why=f"aggregate {concept.total_score.value:.1f} with "
                f"{len(concept.opinions)} opinions",
                cycle_id=concept.cycle_id,
                inputs=(str(concept.id),),
                scores=concept.scoreboard.as_dict(),
                evidence=tuple(
                    f"{o.agent}: {o.verdict} — {o.rationale[:120]}" for o in concept.opinions
                ),
            )
        ctx.logger.info("phase.reflection.evaluated", concepts=len(concepts))
        return concepts

    def _mutation_potential(self, concept: CreativeConcept) -> float:
        """How much life is probably left in an idea that fails.

        High novelty with low execution scores is the ideal mutation candidate:
        the *thought* was good even though this version of it was not.
        """
        novelty = concept.genome.novelty_score.value
        total = concept.total_score.value
        gap = max(0.0, novelty - total)
        return round(min(100.0, 30.0 + gap * 1.2 + concept.disagreement * 20.0), 2)


def _verdict(raw: str) -> Verdict:
    try:
        return Verdict(str(raw).strip().upper())
    except ValueError:
        return Verdict.NEUTRAL


__all__ = [
    "KNOWN_PATTERNS",
    "CalculateCreativeDistance",
    "EvaluateConcepts",
    "EvaluateNovelty",
    "RunCriticSociety",
    "concept_text",
]
