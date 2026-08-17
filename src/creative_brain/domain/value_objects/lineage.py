"""Idea lineage: every concept knows its ancestors.

Lineage is what lets the engine answer "where did this winner actually come
from" three years later, and what lets the mutation engine avoid re-walking a
path that already died.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LineageRelation(StrEnum):
    """Edge types of the creative graph."""

    DERIVED_FROM = "derived_from"
    MUTATED_FROM = "mutated_from"
    MERGED_FROM = "merged_from"
    INSPIRED_BY = "inspired_by"
    RESURRECTED_FROM = "resurrected_from"
    SIMILAR_TO = "similar_to"
    CONTRADICTS = "contradicts"
    SHARES_THEME = "shares_theme"


@dataclass(frozen=True, slots=True)
class LineageLink:
    """One directed edge to an ancestor or sibling."""

    relation: LineageRelation
    ancestor_id: str
    note: str = ""

    def as_dict(self) -> dict[str, str]:
        """Serialisation-friendly view."""
        return {"relation": str(self.relation), "ancestor_id": self.ancestor_id, "note": self.note}


@dataclass(frozen=True, slots=True)
class Lineage:
    """The ordered chain of links that produced an artifact."""

    links: tuple[LineageLink, ...] = ()

    def add(self, relation: LineageRelation, ancestor_id: str, note: str = "") -> Lineage:
        """Return a new lineage with one more edge."""
        return Lineage((*self.links, LineageLink(relation, ancestor_id, note)))

    @property
    def depth(self) -> int:
        """How many transformations separate this idea from its root."""
        return len(self.links)

    @property
    def ancestors(self) -> tuple[str, ...]:
        """Ancestor ids, oldest first."""
        return tuple(link.ancestor_id for link in self.links)

    def has_ancestor(self, ancestor_id: str) -> bool:
        """Whether ``ancestor_id`` appears anywhere in the chain."""
        return ancestor_id in self.ancestors

    def as_list(self) -> list[dict[str, str]]:
        """Serialisation-friendly view."""
        return [link.as_dict() for link in self.links]
