"""Artificial energy gauges that steer the circadian rhythm.

These are **orchestration heuristics**, not a simulation of biology and not a
claim of sentience. They exist so the engine alternates between divergent and
convergent work instead of hammering a single mode until quality collapses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from creative_brain.domain.exceptions import InvalidEnergyLevel

ENERGY_MIN = 0.0
ENERGY_MAX = 100.0


class EnergyKind(StrEnum):
    """The gauges tracked by the circadian state."""

    CREATIVE = "creative_energy"
    RESEARCH = "research_energy"
    CRITICAL = "critical_energy"
    NOVELTY_PRESSURE = "novelty_pressure"
    MEMORY_PRESSURE = "memory_pressure"


@dataclass(frozen=True, slots=True, order=True)
class EnergyLevel:
    """A single 0..100 gauge."""

    value: float

    def __post_init__(self) -> None:
        if not ENERGY_MIN <= float(self.value) <= ENERGY_MAX:
            raise InvalidEnergyLevel(f"energy {self.value} outside [{ENERGY_MIN}, {ENERGY_MAX}]")
        object.__setattr__(self, "value", round(float(self.value), 4))

    @classmethod
    def clamped(cls, value: float) -> EnergyLevel:
        """Build a gauge, clamping instead of raising."""
        return cls(min(ENERGY_MAX, max(ENERGY_MIN, float(value))))

    @classmethod
    def full(cls) -> EnergyLevel:
        """A fully restored gauge."""
        return cls(ENERGY_MAX)

    def spend(self, amount: float) -> EnergyLevel:
        """Consume energy; never drops below zero."""
        return EnergyLevel.clamped(self.value - abs(amount))

    def restore(self, amount: float) -> EnergyLevel:
        """Recover energy; never exceeds 100."""
        return EnergyLevel.clamped(self.value + abs(amount))

    def is_below(self, threshold: float) -> bool:
        """Whether the gauge sits under a policy threshold."""
        return self.value < threshold

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class EnergyProfile:
    """The full set of gauges the circadian policy reads."""

    creative: EnergyLevel = EnergyLevel(100.0)
    research: EnergyLevel = EnergyLevel(100.0)
    critical: EnergyLevel = EnergyLevel(100.0)
    novelty_pressure: EnergyLevel = EnergyLevel(0.0)
    memory_pressure: EnergyLevel = EnergyLevel(0.0)

    @classmethod
    def rested(cls) -> EnergyProfile:
        """The profile the engine wakes up with."""
        return cls()

    def spend(self, kind: EnergyKind, amount: float) -> EnergyProfile:
        """Return a new profile with ``kind`` reduced by ``amount``."""
        return self._with(kind, self.get(kind).spend(amount))

    def restore(self, kind: EnergyKind, amount: float) -> EnergyProfile:
        """Return a new profile with ``kind`` increased by ``amount``."""
        return self._with(kind, self.get(kind).restore(amount))

    def get(self, kind: EnergyKind) -> EnergyLevel:
        """Read one gauge."""
        return {
            EnergyKind.CREATIVE: self.creative,
            EnergyKind.RESEARCH: self.research,
            EnergyKind.CRITICAL: self.critical,
            EnergyKind.NOVELTY_PRESSURE: self.novelty_pressure,
            EnergyKind.MEMORY_PRESSURE: self.memory_pressure,
        }[kind]

    def restored_by_sleep(self, factor: float = 1.0) -> EnergyProfile:
        """Deep sleep refills the productive gauges and drains the pressure gauges."""
        f = max(0.0, factor)
        return EnergyProfile(
            creative=self.creative.restore(60 * f),
            research=self.research.restore(60 * f),
            critical=self.critical.restore(70 * f),
            novelty_pressure=self.novelty_pressure.spend(25 * f),
            memory_pressure=self.memory_pressure.spend(80 * f),
        )

    def as_dict(self) -> dict[str, float]:
        """Serialisation-friendly view."""
        return {kind.value: self.get(kind).value for kind in EnergyKind}

    @classmethod
    def from_mapping(cls, raw: dict[str, float]) -> EnergyProfile:
        """Rebuild a profile from persisted state."""
        return cls(
            creative=EnergyLevel.clamped(raw.get(EnergyKind.CREATIVE.value, 100.0)),
            research=EnergyLevel.clamped(raw.get(EnergyKind.RESEARCH.value, 100.0)),
            critical=EnergyLevel.clamped(raw.get(EnergyKind.CRITICAL.value, 100.0)),
            novelty_pressure=EnergyLevel.clamped(raw.get(EnergyKind.NOVELTY_PRESSURE.value, 0.0)),
            memory_pressure=EnergyLevel.clamped(raw.get(EnergyKind.MEMORY_PRESSURE.value, 0.0)),
        )

    def _with(self, kind: EnergyKind, level: EnergyLevel) -> EnergyProfile:
        field = {
            EnergyKind.CREATIVE: "creative",
            EnergyKind.RESEARCH: "research",
            EnergyKind.CRITICAL: "critical",
            EnergyKind.NOVELTY_PRESSURE: "novelty_pressure",
            EnergyKind.MEMORY_PRESSURE: "memory_pressure",
        }[kind]
        return replace(self, **{field: level})
