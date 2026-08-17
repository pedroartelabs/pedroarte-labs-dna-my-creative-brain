"""How a candidate becomes a number — and when a number is not allowed to win.

Weights are never hidden in code: they arrive from ``config/scoring.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

from creative_brain.domain.exceptions import InvalidCreativeScore
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreCriterion

if TYPE_CHECKING:  # entities import policies; keep the dependency one-way at runtime
    from creative_brain.domain.entities.concept import CreativeConcept

DEFAULT_WEIGHTS: dict[ScoreCriterion, float] = {
    ScoreCriterion.ORIGINALITY: 0.20,
    ScoreCriterion.NARRATIVE_POTENTIAL: 0.15,
    ScoreCriterion.DEPTH: 0.15,
    ScoreCriterion.PLAUSIBILITY: 0.10,
    ScoreCriterion.EMOTIONAL_IMPACT: 0.10,
    ScoreCriterion.COMMERCIAL_POTENTIAL: 0.10,
    ScoreCriterion.AUTHORIAL_IDENTITY: 0.10,
    ScoreCriterion.EXPANDABILITY: 0.05,
    ScoreCriterion.AUDIOVISUAL_POTENTIAL: 0.05,
}


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    """Folds a scoreboard into one number under explicit guard rails."""

    weights: Mapping[ScoreCriterion, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    #: A candidate cannot win on commercial appeal alone (article 13).
    max_commercial_share: float = 0.25
    #: Below this, an idea is a near-copy and is disqualified regardless of score.
    min_originality: float = 35.0
    #: A blocking rejection from any agent caps the final score.
    blocked_score_ceiling: float = 45.0

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if total <= 0:
            raise InvalidCreativeScore("scoring weights must sum to a positive number")
        commercial = self.weights.get(ScoreCriterion.COMMERCIAL_POTENTIAL, 0.0) / total
        if commercial > self.max_commercial_share:
            raise InvalidCreativeScore(
                f"commercial weight {commercial:.2f} exceeds the "
                f"{self.max_commercial_share:.2f} ceiling: market score must never "
                "decide artistic quality on its own"
            )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, float], **kwargs: float) -> ScoringPolicy:
        """Build from raw configuration, ignoring unknown criteria."""
        known = {c.value for c in ScoreCriterion}
        weights = {ScoreCriterion(k): float(v) for k, v in raw.items() if k in known}
        return cls(weights=weights or dict(DEFAULT_WEIGHTS), **kwargs)  # type: ignore[arg-type]

    def total_for(self, concept: CreativeConcept) -> CreativeScore:
        """Weighted aggregate, capped when the society raised a blocking objection."""
        total = concept.scoreboard.weighted_total(self.weights)
        if concept.is_blocked:
            return CreativeScore.clamped(min(total.value, self.blocked_score_ceiling))
        return total

    def disqualifies(self, concept: CreativeConcept) -> str | None:
        """Return a reason when a candidate must not advance, regardless of score."""
        originality = concept.scoreboard.get(ScoreCriterion.ORIGINALITY).value
        if originality < self.min_originality:
            return (
                f"originality {originality:.0f} below the floor {self.min_originality:.0f} "
                "(article 3: influence must never become copy)"
            )
        if concept.genome.creative_distance.is_near_copy:
            return (
                f"creative distance {concept.genome.creative_distance.value:.0f} indicates a "
                "near-copy of existing work"
            )
        return None
