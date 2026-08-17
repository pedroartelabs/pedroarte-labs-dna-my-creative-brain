"""Mutation operators — how a dead idea gets a second, different life.

A mutation must change a *structural* dimension. Rewording is not mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from creative_brain.domain.policies.lifecycle import REVIVABLE_STAGES

if TYPE_CHECKING:  # entities import policies; keep the dependency one-way at runtime
    from creative_brain.domain.entities.concept import CreativeConcept


class MutationOperator(StrEnum):
    """The structural transformations the mutation engine may apply."""

    CHANGE_PROTAGONIST = "change_protagonist"
    CHANGE_SCALE = "change_scale"
    CHANGE_PERIOD = "change_period"
    REMOVE_TECHNOLOGY = "remove_technology"
    INVERT_RULE = "invert_rule"
    INVERT_CONSEQUENCE = "invert_consequence"
    MERGE_WITH_OTHER_SEED = "merge_with_other_seed"
    CHANGE_COUNTRY = "change_country"
    CHANGE_SOCIAL_CLASS = "change_social_class"
    CHANGE_NARRATIVE_POINT_OF_VIEW = "change_narrative_point_of_view"


#: Human-readable instruction handed to the mutation agent for each operator.
OPERATOR_INSTRUCTION: dict[MutationOperator, str] = {
    MutationOperator.CHANGE_PROTAGONIST: (
        "Keep the world, change who carries the story: move to the person the "
        "original treated as scenery."
    ),
    MutationOperator.CHANGE_SCALE: (
        "Keep the rule, change the scale: from one family to a nation, or from a "
        "nation to a single apartment."
    ),
    MutationOperator.CHANGE_PERIOD: (
        "Keep the mechanism, move it in time until the technology stops being the point."
    ),
    MutationOperator.REMOVE_TECHNOLOGY: (
        "Delete the technology entirely. If the drama dies with it, the drama was never there."
    ),
    MutationOperator.INVERT_RULE: "Invert the central rule of the world and follow what breaks.",
    MutationOperator.INVERT_CONSEQUENCE: (
        "Keep the premise, invert who pays the price and who profits."
    ),
    MutationOperator.MERGE_WITH_OTHER_SEED: (
        "Fuse this idea with an unrelated seed until a third, unfamiliar thing appears."
    ),
    MutationOperator.CHANGE_COUNTRY: (
        "Relocate the premise into a different social contract and let the "
        "institutions rewrite the plot."
    ),
    MutationOperator.CHANGE_SOCIAL_CLASS: (
        "Move the premise across class lines; the same rule means a different life."
    ),
    MutationOperator.CHANGE_NARRATIVE_POINT_OF_VIEW: (
        "Tell it from the position that benefits from the system instead of the one that suffers."
    ),
}


@dataclass(frozen=True, slots=True)
class MutationPolicy:
    """Decides which dead ideas deserve mutation, and how far they may be pushed."""

    enabled: bool = True
    min_mutation_potential: float = 40.0
    max_lineage_depth: int = 5
    max_mutations_per_cycle: int = 8

    def is_mutable(self, concept: CreativeConcept) -> bool:
        """Whether a concept may enter the mutation pool."""
        if not self.enabled:
            return False
        if concept.stage not in REVIVABLE_STAGES:
            return False
        if concept.lineage.depth >= self.max_lineage_depth:
            return False
        return concept.mutation_potential >= self.min_mutation_potential

    def rank(self, concepts: list[CreativeConcept]) -> list[CreativeConcept]:
        """Order dead ideas by how much life is probably left in them."""
        return sorted(
            (c for c in concepts if self.is_mutable(c)),
            key=lambda c: (c.mutation_potential, -c.lineage.depth),
            reverse=True,
        )[: self.max_mutations_per_cycle]

    def instruction_for(self, operator: MutationOperator) -> str:
        """The prompt fragment describing what the operator must actually change."""
        return OPERATOR_INSTRUCTION[operator]
