"""Composable specifications used to query and filter creative artifacts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.policies.lifecycle import REVIVABLE_STAGES, CreativeStage
from creative_brain.domain.value_objects.creative_distance import CreativeZone

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """A named, composable predicate."""

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Whether the candidate matches."""

    def __and__(self, other: Specification[T]) -> Specification[T]:
        return _And(self, other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        return _Or(self, other)

    def __invert__(self) -> Specification[T]:
        return _Not(self)

    def filter(self, candidates: list[T]) -> list[T]:
        """Keep only the matching candidates."""
        return [c for c in candidates if self.is_satisfied_by(c)]


@dataclass(frozen=True)
class _And(Specification[T]):
    left: Specification[T]
    right: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        """Both sides must match."""
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)


@dataclass(frozen=True)
class _Or(Specification[T]):
    left: Specification[T]
    right: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        """Either side may match."""
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)


@dataclass(frozen=True)
class _Not(Specification[T]):
    inner: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        """Invert the inner specification."""
        return not self.inner.is_satisfied_by(candidate)


@dataclass(frozen=True)
class InStage(Specification[CreativeConcept]):
    """Concepts sitting in one of the given stages."""

    stages: frozenset[CreativeStage]

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match on lifecycle stage."""
        return candidate.stage in self.stages


@dataclass(frozen=True)
class IsAlive(Specification[CreativeConcept]):
    """Concepts still competing on the main line."""

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match anything not rejected, archived, buried or asleep."""
        return candidate.is_alive


@dataclass(frozen=True)
class IsRevivable(Specification[CreativeConcept]):
    """Dead ideas Dream Mode is allowed to look at again."""

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match rejected, archived, buried, sleeping or pooled ideas."""
        return candidate.stage in REVIVABLE_STAGES


@dataclass(frozen=True)
class InZone(Specification[CreativeConcept]):
    """Concepts whose creative distance falls in a given exploration zone."""

    zone: CreativeZone

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match on the genome's creative zone."""
        return candidate.genome.creative_distance.zone is self.zone


@dataclass(frozen=True)
class ScoredAbove(Specification[CreativeConcept]):
    """Concepts whose aggregate score clears a threshold."""

    threshold: float

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match on the persisted aggregate score."""
        return candidate.total_score.value >= self.threshold


@dataclass(frozen=True)
class HasTheme(Specification[CreativeConcept]):
    """Concepts carrying a given theme (case-insensitive)."""

    theme: str

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match on the theme list."""
        wanted = self.theme.strip().lower()
        return any(t.strip().lower() == wanted for t in candidate.themes)


@dataclass(frozen=True)
class FromCycle(Specification[CreativeConcept]):
    """Concepts produced during a specific cycle."""

    cycle_id: str

    def is_satisfied_by(self, candidate: CreativeConcept) -> bool:
        """Match on cycle id."""
        return candidate.cycle_id == self.cycle_id


__all__ = [
    "FromCycle",
    "HasTheme",
    "InStage",
    "InZone",
    "IsAlive",
    "IsRevivable",
    "ScoredAbove",
    "Specification",
]
