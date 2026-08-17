"""Creative distance: how far an idea sits from the established creative DNA.

The scale is deliberately blunt because it is a *steering* signal, not a
measurement of quality::

    0    near-copy of something already in the canon
    25   variation on a known pattern
    50   familiar and new at the same time
    75   highly original
    100  completely detached from the DNA
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from creative_brain.domain.exceptions import InvalidCreativeDistance

DISTANCE_MIN = 0.0
DISTANCE_MAX = 100.0


class CreativeZone(StrEnum):
    """The three exploration territories the engine allocates effort across."""

    COMFORT_ZONE = "COMFORT_ZONE"
    EDGE_ZONE = "EDGE_ZONE"
    UNKNOWN_ZONE = "UNKNOWN_ZONE"


@dataclass(frozen=True, slots=True, order=True)
class CreativeDistance:
    """Distance of an idea from the CORE_DNA, on the 0..100 scale."""

    value: float

    # Zone boundaries are domain knowledge, but the *allocation* across zones is
    # configuration (see config/scoring.yaml -> exploration).
    COMFORT_MAX = 40.0
    EDGE_MAX = 75.0

    def __post_init__(self) -> None:
        if not DISTANCE_MIN <= float(self.value) <= DISTANCE_MAX:
            raise InvalidCreativeDistance(
                f"creative distance {self.value} outside [{DISTANCE_MIN}, {DISTANCE_MAX}]"
            )
        object.__setattr__(self, "value", round(float(self.value), 4))

    @classmethod
    def clamped(cls, value: float) -> CreativeDistance:
        """Build a distance, clamping instead of raising."""
        return cls(min(DISTANCE_MAX, max(DISTANCE_MIN, float(value))))

    @property
    def zone(self) -> CreativeZone:
        """The exploration territory this distance falls into."""
        if self.value <= self.COMFORT_MAX:
            return CreativeZone.COMFORT_ZONE
        if self.value <= self.EDGE_MAX:
            return CreativeZone.EDGE_ZONE
        return CreativeZone.UNKNOWN_ZONE

    @property
    def is_near_copy(self) -> bool:
        """Article 3 of the constitution: influence must never become copy."""
        return self.value < 12.0

    def __float__(self) -> float:
        return self.value


def zone_for(value: float) -> CreativeZone:
    """Convenience wrapper used by policies that only carry a raw float."""
    return CreativeDistance.clamped(value).zone
