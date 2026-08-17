"""The selection engine: who survives each round, and why.

Selection is not a pure ranking. Two extra pressures apply:

* **diversity** — a round that keeps five variations of one idea has failed;
* **constitution** — a disqualified candidate never survives, whatever it scored.
"""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.tournament import TournamentFunnel
from creative_brain.domain.exceptions import EmptyTournamentError
from creative_brain.domain.policies.scoring import ScoringPolicy
from creative_brain.domain.services.evaluation import DiversityService
from creative_brain.domain.services.similarity import max_similarity


@dataclass(frozen=True, slots=True)
class SelectionOutcome:
    """One round's verdict."""

    survivors: tuple[CreativeConcept, ...]
    eliminated: tuple[CreativeConcept, ...]
    reasons: dict[str, str]


@dataclass(frozen=True, slots=True)
class TournamentService:
    """Runs elimination rounds under a scoring policy and a diversity guard."""

    scoring: ScoringPolicy
    diversity: DiversityService = DiversityService()
    #: A survivor may not be this similar to an already-selected survivor.
    max_similarity_between_survivors: float = 0.60
    #: How strongly redundancy penalises an otherwise strong candidate.
    redundancy_penalty: float = 18.0

    def select(self, candidates: list[CreativeConcept], keep: int) -> SelectionOutcome:
        """Keep the best ``keep`` candidates, penalising redundancy."""
        if not candidates:
            raise EmptyTournamentError("cannot select survivors from an empty pool")
        keep = max(1, min(keep, len(candidates)))

        ranked = sorted(candidates, key=self._sort_key, reverse=True)
        survivors: list[CreativeConcept] = []
        eliminated: list[CreativeConcept] = []
        reasons: dict[str, str] = {}

        for candidate in ranked:
            disqualification = self.scoring.disqualifies(candidate)
            if disqualification:
                eliminated.append(candidate)
                reasons[str(candidate.id)] = disqualification
                continue
            if len(survivors) >= keep:
                eliminated.append(candidate)
                reasons[str(candidate.id)] = (
                    f"ranked {ranked.index(candidate) + 1} of {len(ranked)}; "
                    f"only {keep} slots in this round"
                )
                continue
            redundancy = max_similarity(
                self._text(candidate), [self._text(s) for s in survivors]
            )
            if redundancy >= self.max_similarity_between_survivors:
                eliminated.append(candidate)
                reasons[str(candidate.id)] = (
                    f"{redundancy:.0%} similar to a candidate already selected "
                    "(article 11: disguised repetition)"
                )
                continue
            survivors.append(candidate)

        # A round must never come back empty: if every candidate was redundant or
        # disqualified, the strongest one is promoted so the cycle can complete.
        if not survivors:
            best = ranked[0]
            survivors.append(best)
            eliminated = [c for c in eliminated if c is not best]
            reasons[str(best.id)] = "promoted by fallback: every candidate was disqualified"

        return SelectionOutcome(tuple(survivors), tuple(eliminated), reasons)

    def run_funnel(
        self, pool: list[CreativeConcept], funnel: TournamentFunnel
    ) -> list[SelectionOutcome]:
        """Walk every step of the funnel, feeding survivors into the next round."""
        outcomes: list[SelectionOutcome] = []
        current = pool
        for step in funnel.steps:
            outcome = self.select(current, step.survivors)
            outcomes.append(outcome)
            current = list(outcome.survivors)
        return outcomes

    def batch_diversity(self, candidates: list[CreativeConcept]) -> float:
        """Diversity of a candidate pool, 0..100."""
        return self.diversity.score([self._text(c) for c in candidates])

    def _sort_key(self, concept: CreativeConcept) -> tuple[float, float, float]:
        total = self.scoring.total_for(concept).value
        return (total, concept.genome.novelty_score.value, concept.support_ratio)

    @staticmethod
    def _text(concept: CreativeConcept) -> str:
        return " ".join(
            filter(
                None,
                (
                    concept.title,
                    concept.logline,
                    concept.central_question,
                    concept.artifacts.get("premise", ""),
                    " ".join(concept.themes),
                ),
            )
        )
