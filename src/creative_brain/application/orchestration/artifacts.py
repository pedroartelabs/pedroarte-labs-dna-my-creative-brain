"""Writes the human-readable record of a cycle to ``outputs/``.

Article 14 of the constitution: every relevant creative decision must be
explainable through persisted artifacts. This is where that promise is kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from creative_brain.application.context import BrainContext
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import Dream
from creative_brain.domain.entities.project import CreativeProject
from creative_brain.domain.entities.tournament import CreativeTournament


@dataclass
class CycleArtifactWriter:
    """Persists observations, questions, seeds, concepts and the winner."""

    context: BrainContext

    def write_phase_inputs(self, *, cycle_id: str) -> None:
        """Dump the raw material of the cycle."""
        ctx = self.context
        repo = ctx.repositories
        ctx.output.write_json(
            cycle_id,
            "observations/observations.json",
            [o.as_dict() for o in repo.observations.list_for_cycle(cycle_id)],
        )
        ctx.output.write_json(
            cycle_id,
            "questions/questions.json",
            [q.as_dict() for q in repo.questions.list_for_cycle(cycle_id)],
        )
        ctx.output.write_json(
            cycle_id,
            "seeds/seeds.json",
            [s.as_dict() for s in repo.seeds.list_for_cycle(cycle_id)],
        )

    def write_concepts(self, *, cycle_id: str, concepts: list[CreativeConcept]) -> None:
        """Dump every concept plus a readable leaderboard."""
        ctx = self.context
        ctx.output.write_json(
            cycle_id, "concepts/concepts.json", [c.as_dict() for c in concepts]
        )
        ranked = sorted(concepts, key=lambda c: c.total_score.value, reverse=True)
        lines = [
            "# Leaderboard do ciclo",
            "",
            "| # | Título | Score | Novidade | Distância | Zona | Mecanismo | Estágio |",
            "|---|--------|-------|----------|-----------|------|-----------|---------|",
        ]
        for index, concept in enumerate(ranked, start=1):
            lines.append(
                f"| {index} | {concept.title} | {concept.total_score.value:.1f} "
                f"| {concept.genome.novelty_score.value:.1f} "
                f"| {concept.genome.creative_distance.value:.1f} "
                f"| {concept.genome.creative_distance.zone} "
                f"| {concept.genome.origin.mechanism} | {concept.stage} |"
            )
        ctx.output.write(cycle_id, "concepts/leaderboard.md", "\n".join(lines) + "\n")

        rejected = [c for c in concepts if c.rejection_reasons]
        ctx.output.write_json(
            cycle_id,
            "rejected/rejected.json",
            [
                {
                    "id": str(c.id),
                    "title": c.title,
                    "concept": c.logline,
                    "created_at": c.created_at,
                    "rejected_at": c.rejected_at,
                    "scores": c.scoreboard.as_dict(),
                    "rejection_reasons": list(c.rejection_reasons),
                    "agent_feedback": [o.as_dict() for o in c.opinions],
                    "mutation_potential": c.mutation_potential,
                    "similar_ideas": [link.ancestor_id for link in c.lineage.links],
                }
                for c in rejected
            ],
        )

    def write_tournament(self, *, cycle_id: str, tournament: CreativeTournament) -> None:
        """Dump the funnel and each round."""
        self.context.output.write_json(
            cycle_id, "tournament/tournament.json", tournament.as_dict()
        )

    def write_finalists(self, *, cycle_id: str, finalists: list[CreativeConcept]) -> None:
        """Dump the last few standing."""
        self.context.output.write_json(
            cycle_id, "finalists/finalists.json", [c.as_dict() for c in finalists]
        )

    def write_winner(
        self, *, cycle_id: str, concept: CreativeConcept, project: CreativeProject
    ) -> None:
        """Write the full winner package a production engine can consume."""
        ctx = self.context
        artifacts = concept.artifacts
        ctx.output.write(cycle_id, "winner/concept.md", _md("Conceito", concept.logline))
        ctx.output.write(
            cycle_id, "winner/premise.md", _md("Premissa", artifacts.get("premise", ""))
        )
        ctx.output.write(cycle_id, "winner/pitch.md", _md("Pitch", artifacts.get("pitch", "")))
        ctx.output.write(
            cycle_id, "winner/synopsis.md", _md("Sinopse", artifacts.get("synopsis", ""))
        )
        ctx.output.write(
            cycle_id, "winner/world_bible.md", _md("Bíblia do mundo", artifacts.get("world_bible", ""))
        )
        ctx.output.write(
            cycle_id, "winner/characters.md", _md("Personagens", artifacts.get("characters", ""))
        )
        ctx.output.write_yamlish(cycle_id, "genome/creative_genome.yaml", concept.genome.as_dict())
        ctx.output.write_json(
            cycle_id,
            "winner/evaluation.json",
            {
                "concept_id": str(concept.id),
                "title": concept.title,
                "total_score": concept.total_score.value,
                "scores": concept.scoreboard.as_dict(),
                "support_ratio": concept.support_ratio,
                "disagreement": concept.disagreement,
                "opinions": [o.as_dict() for o in concept.opinions],
            },
        )
        ctx.output.write_json(
            cycle_id, "winner/execution_manifest.json", project.execution_manifest()
        )

    def write_dream(self, *, cycle_id: str, dream: Dream) -> None:
        """Dump the dream session."""
        self.context.output.write_json(cycle_id, "learning/dream.json", dream.as_dict())

    def write_learning(self, *, cycle_id: str, payload: dict[str, Any]) -> None:
        """Dump the end-of-cycle learning report."""
        self.context.output.write_json(cycle_id, "learning/learning.json", payload)

    def write_runtime(self, *, cycle_id: str, payload: dict[str, Any]) -> None:
        """Dump the runtime manifest: phases, timings, budgets, metrics, seed."""
        self.context.output.write_json(cycle_id, "runtime/runtime.json", payload)


def _md(title: str, body: str) -> str:
    return f"# {title}\n\n{body.strip()}\n" if body.strip() else f"# {title}\n\n_(não gerado)_\n"


__all__ = ["CycleArtifactWriter"]
