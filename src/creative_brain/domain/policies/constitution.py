"""The creative constitution, expressed as executable checks.

``CREATIVE_CONSTITUTION.md`` is the prose version for humans. This module is the
version the engine is actually held to: a candidate that violates a
non-negotiable article cannot be approved, no matter how high it scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from creative_brain.domain.value_objects.scores import ScoreCriterion

if TYPE_CHECKING:  # entities import policies; keep the dependency one-way at runtime
    from creative_brain.domain.entities.concept import CreativeConcept


@dataclass(frozen=True, slots=True)
class ConstitutionArticle:
    """One numbered article and whether breaking it is fatal."""

    number: int
    text: str
    blocking: bool


ARTICLES: tuple[ConstitutionArticle, ...] = (
    ConstitutionArticle(1, "Originality outranks productivity.", True),
    ConstitutionArticle(2, "No idea may exist only to hit a quota.", False),
    ConstitutionArticle(3, "Influence must never become copy.", True),
    ConstitutionArticle(4, "Concepts must have consequences.", True),
    ConstitutionArticle(5, "Worlds must obey their own rules.", True),
    ConstitutionArticle(6, "Technology never replaces human drama.", True),
    ConstitutionArticle(7, "Strangeness must carry meaning.", False),
    ConstitutionArticle(8, "The ending must widen or reinterpret the premise.", False),
    ConstitutionArticle(9, "Every work needs a central question.", True),
    ConstitutionArticle(10, "The engine must be able to reject its own ideas.", True),
    ConstitutionArticle(
        11, "Thematic repetition is allowed; disguised conceptual repetition is not.", True
    ),
    ConstitutionArticle(12, "The system must keep seeking unknown creative territory.", False),
    ConstitutionArticle(13, "Quality must beat quantity.", True),
    ConstitutionArticle(
        14, "Every relevant creative decision must be explainable by persisted artifacts.", True
    ),
)


@dataclass(frozen=True, slots=True)
class ConstitutionPolicy:
    """Checks a candidate against the blocking articles."""

    min_depth_for_consequence: float = 30.0
    min_emotional_impact: float = 30.0

    def violations(self, concept: CreativeConcept) -> tuple[str, ...]:
        """Every blocking article this candidate breaks, as human-readable reasons."""
        found: list[str] = []

        if not concept.central_question.strip():
            found.append("article 9: no central question was ever formulated")

        if concept.genome.creative_distance.is_near_copy:
            found.append(
                f"article 3: creative distance {concept.genome.creative_distance.value:.0f} "
                "means this is a near-copy"
            )

        depth = concept.scoreboard.get(ScoreCriterion.DEPTH).value
        if depth < self.min_depth_for_consequence:
            found.append(f"article 4: depth {depth:.0f} — the concept has no consequences")

        emotional = concept.scoreboard.get(ScoreCriterion.EMOTIONAL_IMPACT).value
        if emotional < self.min_emotional_impact:
            found.append(
                f"article 6: emotional impact {emotional:.0f} — the technology is doing the "
                "work that human drama should be doing"
            )

        if not concept.opinions:
            found.append("article 14: no agent evidence was persisted for this candidate")

        return tuple(found)

    def approves(self, concept: CreativeConcept) -> bool:
        """Whether the candidate is constitutionally allowed to be approved."""
        return not self.violations(concept)

    @staticmethod
    def article(number: int) -> ConstitutionArticle:
        """Look up an article by number."""
        return next(a for a in ARTICLES if a.number == number)
