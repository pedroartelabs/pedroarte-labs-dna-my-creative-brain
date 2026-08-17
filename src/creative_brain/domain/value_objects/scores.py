"""Scoring value objects.

All creative measurements live on a single canonical 0..100 scale so that
weights configured in ``config/scoring.yaml`` stay comparable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from creative_brain.domain.exceptions import InvalidCreativeScore

SCORE_MIN = 0.0
SCORE_MAX = 100.0


class ScoreCriterion(StrEnum):
    """The criteria a candidate is judged on. Weights are configuration, not code."""

    ORIGINALITY = "originality"
    NARRATIVE_POTENTIAL = "narrative_potential"
    DEPTH = "depth"
    PLAUSIBILITY = "plausibility"
    EMOTIONAL_IMPACT = "emotional_impact"
    COMMERCIAL_POTENTIAL = "commercial_potential"
    AUTHORIAL_IDENTITY = "authorial_identity"
    EXPANDABILITY = "expandability"
    AUDIOVISUAL_POTENTIAL = "audiovisual_potential"


@dataclass(frozen=True, slots=True, order=True)
class CreativeScore:
    """A single measurement in the 0..100 range."""

    value: float

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)) or self.value != self.value:  # NaN guard
            raise InvalidCreativeScore(f"score must be a real number, got {self.value!r}")
        if not SCORE_MIN <= float(self.value) <= SCORE_MAX:
            raise InvalidCreativeScore(f"score {self.value} outside [{SCORE_MIN}, {SCORE_MAX}]")
        object.__setattr__(self, "value", round(float(self.value), 4))

    @classmethod
    def clamped(cls, value: float) -> CreativeScore:
        """Build a score, clamping instead of raising. Used when folding noisy agent output."""
        return cls(min(SCORE_MAX, max(SCORE_MIN, float(value))))

    @classmethod
    def zero(cls) -> CreativeScore:
        """The lowest possible score."""
        return cls(SCORE_MIN)

    def blend(self, other: CreativeScore, weight: float) -> CreativeScore:
        """Linearly interpolate towards ``other`` by ``weight`` in 0..1."""
        w = min(1.0, max(0.0, weight))
        return CreativeScore.clamped(self.value * (1 - w) + other.value * w)

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class ScoreBoard:
    """An immutable set of criterion scores plus the weighted aggregate."""

    scores: Mapping[ScoreCriterion, CreativeScore]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scores", dict(self.scores))

    def get(self, criterion: ScoreCriterion) -> CreativeScore:
        """Return a criterion score, or zero when the criterion was not measured."""
        return self.scores.get(criterion, CreativeScore.zero())

    def weighted_total(self, weights: Mapping[ScoreCriterion, float]) -> CreativeScore:
        """Fold the board into a single score using externally configured weights."""
        total_weight = sum(weights.values())
        if total_weight <= 0:
            raise InvalidCreativeScore("scoring weights must sum to a positive number")
        weighted = sum(self.get(c).value * w for c, w in weights.items())
        return CreativeScore.clamped(weighted / total_weight)

    def as_dict(self) -> dict[str, float]:
        """Serialisation-friendly view."""
        return {str(c): s.value for c, s in self.scores.items()}

    def merge(self, other: ScoreBoard) -> ScoreBoard:
        """Average overlapping criteria; keep the union of both boards."""
        merged: dict[ScoreCriterion, CreativeScore] = dict(self.scores)
        for criterion, score in other.scores.items():
            if criterion in merged:
                merged[criterion] = CreativeScore.clamped((merged[criterion].value + score.value) / 2)
            else:
                merged[criterion] = score
        return ScoreBoard(merged)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, float]) -> ScoreBoard:
        """Build a board from raw agent output, ignoring unknown criteria."""
        known = {c.value for c in ScoreCriterion}
        return cls(
            {
                ScoreCriterion(name): CreativeScore.clamped(value)
                for name, value in raw.items()
                if name in known
            }
        )
