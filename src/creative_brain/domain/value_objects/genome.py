"""The creative genome: the traceable "how was this thought" of an idea.

Article 14 of the constitution requires every relevant creative decision to be
explainable through persisted artifacts. The genome is where an idea records
*which cognitive mechanism produced it*, so the engine can later learn which
mechanisms actually win.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.domain.value_objects.creative_distance import CreativeDistance
from creative_brain.domain.value_objects.scores import CreativeScore


class OriginMechanism(StrEnum):
    """The cognitive mechanisms that can give birth to an idea."""

    OBSERVATION = "observation"
    RESEARCH = "research"
    CURIOSITY = "curiosity"
    WHAT_IF = "what_if"
    COLLISION = "collision"
    INVERSION = "inversion"
    PARADOX = "paradox"
    CONSEQUENCE = "consequence"
    DREAM = "dream"
    MUTATION = "mutation"
    UNKNOWN_ZONE = "unknown_zone"


@dataclass(frozen=True, slots=True)
class GenomeOrigin:
    """Which mechanisms fired, and with what raw material."""

    mechanism: OriginMechanism
    observation: str | None = None
    inversion: str | None = None
    paradox: str | None = None
    collision: tuple[str, ...] = ()
    research: str | None = None
    dream: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "mechanism": str(self.mechanism),
            "observation": self.observation,
            "inversion": self.inversion,
            "paradox": self.paradox,
            "collision": list(self.collision),
            "research": self.research,
            "dream": self.dream,
        }


@dataclass(frozen=True, slots=True)
class CreativeGenome:
    """The full genetic record attached to every candidate."""

    origin: GenomeOrigin
    themes: tuple[str, ...] = ()
    tone: tuple[str, ...] = ()
    structure: tuple[str, ...] = ()
    creative_distance: CreativeDistance = field(default_factory=lambda: CreativeDistance(50.0))
    novelty_score: CreativeScore = field(default_factory=lambda: CreativeScore(50.0))
    commercial_score: CreativeScore = field(default_factory=lambda: CreativeScore(50.0))
    identity_score: CreativeScore = field(default_factory=lambda: CreativeScore(50.0))

    def with_scores(
        self,
        *,
        novelty: CreativeScore | None = None,
        commercial: CreativeScore | None = None,
        identity: CreativeScore | None = None,
        distance: CreativeDistance | None = None,
    ) -> CreativeGenome:
        """Return a copy with evaluation results folded in."""
        return CreativeGenome(
            origin=self.origin,
            themes=self.themes,
            tone=self.tone,
            structure=self.structure,
            creative_distance=distance or self.creative_distance,
            novelty_score=novelty or self.novelty_score,
            commercial_score=commercial or self.commercial_score,
            identity_score=identity or self.identity_score,
        )

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view, matching ``creative_genome.yaml``."""
        return {
            "origin": self.origin.as_dict(),
            "themes": list(self.themes),
            "tone": list(self.tone),
            "structure": list(self.structure),
            "creative_distance": self.creative_distance.value,
            "creative_zone": str(self.creative_distance.zone),
            "novelty_score": self.novelty_score.value,
            "commercial_score": self.commercial_score.value,
            "identity_score": self.identity_score.value,
        }
