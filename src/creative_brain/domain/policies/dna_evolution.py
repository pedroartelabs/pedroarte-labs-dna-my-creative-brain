"""What the engine may learn about itself — and what stays off limits.

Self-evaluation is not self-modification. The engine may rewrite EVOLVING_DNA;
it may never touch CORE_DNA, the constitution, security policy or its own code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.domain.exceptions import AutonomyBoundaryViolation, ImmutableCoreDnaViolation
from creative_brain.domain.value_objects.dna import EvolvingDna


class ProtectedAsset(StrEnum):
    """Assets the autonomous loop is never allowed to modify."""

    CORE_DNA = "CORE_DNA"
    CREATIVE_CONSTITUTION = "CREATIVE_CONSTITUTION"
    SECURITY_POLICY = "SECURITY_POLICY"
    SOURCE_CODE = "SOURCE_CODE"
    REPOSITORY_PERMISSIONS = "REPOSITORY_PERMISSIONS"
    CREDENTIALS = "CREDENTIALS"


@dataclass(frozen=True, slots=True)
class DnaEvolutionPolicy:
    """Bounds on autonomous learning."""

    enabled: bool = True
    max_new_entries_per_cycle: int = 6
    min_evidence_per_entry: int = 1
    #: Learning may nudge scoring weights, but only inside this band.
    max_weight_drift: float = 0.05
    protected: frozenset[ProtectedAsset] = field(
        default_factory=lambda: frozenset(ProtectedAsset)
    )

    def assert_writable(self, asset: str) -> None:
        """Raise when the engine tries to write something outside its autonomy."""
        normalised = asset.strip().upper()
        if normalised in {str(p) for p in self.protected}:
            if normalised == str(ProtectedAsset.CORE_DNA):
                raise ImmutableCoreDnaViolation(
                    "CORE_DNA is protected: autonomous learning must target EVOLVING_DNA"
                )
            raise AutonomyBoundaryViolation(
                f"'{asset}' is outside the creative domain's autonomy envelope"
            )

    def apply(
        self,
        current: EvolvingDna,
        *,
        discoveries: tuple[str, ...] = (),
        emergent_patterns: tuple[str, ...] = (),
        promising_territories: tuple[str, ...] = (),
        saturated_themes: tuple[str, ...] = (),
        successful_combinations: tuple[str, ...] = (),
        techniques: tuple[str, ...] = (),
        reason: str = "",
        at: str = "",
    ) -> EvolvingDna:
        """Fold a learning proposal into EVOLVING_DNA, capped per cycle."""
        if not self.enabled:
            return current
        cap = self.max_new_entries_per_cycle
        return current.learn(
            discoveries=discoveries[:cap],
            emergent_patterns=emergent_patterns[:cap],
            promising_territories=promising_territories[:cap],
            saturated_themes=saturated_themes[:cap],
            successful_combinations=successful_combinations[:cap],
            techniques=techniques[:cap],
            reason=reason,
            at=at,
        )

    def clamp_weight(self, current: float, proposed: float) -> float:
        """Keep autonomous weight tuning inside the allowed drift band."""
        low, high = current - self.max_weight_drift, current + self.max_weight_drift
        return max(low, min(high, proposed))
