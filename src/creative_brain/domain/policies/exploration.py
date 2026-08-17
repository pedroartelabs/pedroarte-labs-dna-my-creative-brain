"""How effort is spread across comfort, edge and unknown territory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from creative_brain.domain.exceptions import DomainRuleViolation
from creative_brain.domain.value_objects.creative_distance import CreativeZone


@dataclass(frozen=True, slots=True)
class ExplorationPolicy:
    """The zone allocation. Never hard-coded — see ``config/scoring.yaml``."""

    comfort: float = 0.30
    edge: float = 0.50
    unknown: float = 0.20
    unknown_zone_enabled: bool = True

    def __post_init__(self) -> None:
        total = self.comfort + self.edge + self.unknown
        if abs(total - 1.0) > 1e-6:
            raise DomainRuleViolation(f"exploration allocation must sum to 1.0, got {total:.4f}")
        if min(self.comfort, self.edge, self.unknown) < 0:
            raise DomainRuleViolation("exploration allocation cannot be negative")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, float], *, unknown_enabled: bool = True) -> (
        ExplorationPolicy
    ):
        """Build from configuration."""
        policy = cls(
            comfort=float(raw.get("comfort", 0.30)),
            edge=float(raw.get("edge", 0.50)),
            unknown=float(raw.get("unknown", 0.20)),
            unknown_zone_enabled=unknown_enabled,
        )
        return policy.without_unknown() if not unknown_enabled else policy

    def without_unknown(self) -> ExplorationPolicy:
        """Redistribute the unknown share when the feature flag is off."""
        if self.unknown == 0:
            return self
        freed = self.unknown
        base = self.comfort + self.edge
        if base <= 0:
            return ExplorationPolicy(0.5, 0.5, 0.0, unknown_zone_enabled=False)
        return ExplorationPolicy(
            comfort=self.comfort + freed * (self.comfort / base),
            edge=self.edge + freed * (self.edge / base),
            unknown=0.0,
            unknown_zone_enabled=False,
        )

    def share(self, zone: CreativeZone) -> float:
        """The configured share for one zone."""
        return {
            CreativeZone.COMFORT_ZONE: self.comfort,
            CreativeZone.EDGE_ZONE: self.edge,
            CreativeZone.UNKNOWN_ZONE: self.unknown,
        }[zone]

    def allocate(self, total: int) -> dict[CreativeZone, int]:
        """Split ``total`` slots across the three zones, never losing a slot to rounding."""
        if total <= 0:
            return dict.fromkeys(CreativeZone, 0)
        raw = {zone: self.share(zone) * total for zone in CreativeZone}
        allocation = {zone: int(value) for zone, value in raw.items()}
        remainder = total - sum(allocation.values())
        # Hand leftovers to the zones with the largest fractional part.
        for zone, _ in sorted(raw.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True):
            if remainder <= 0:
                break
            allocation[zone] += 1
            remainder -= 1
        return allocation

    def target_distance(self, zone: CreativeZone) -> float:
        """The distance the generator should aim for inside a zone."""
        return {
            CreativeZone.COMFORT_ZONE: 25.0,
            CreativeZone.EDGE_ZONE: 58.0,
            CreativeZone.UNKNOWN_ZONE: 88.0,
        }[zone]

    def as_dict(self) -> dict[str, float]:
        """Serialisation-friendly view."""
        return {"comfort": self.comfort, "edge": self.edge, "unknown": self.unknown}
