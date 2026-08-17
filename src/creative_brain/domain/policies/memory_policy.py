"""What gets remembered, what decays, and what is never thrown away."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.domain.entities.memory import MemoryKind, MemoryRecord


@dataclass(frozen=True, slots=True)
class MemoryPolicy:
    """Rules for consolidation, decay and retrieval."""

    #: Episodic records fade; principles and the graveyard never do.
    episodic_decay_per_cycle: float = 0.92
    #: Below this salience an episodic record stops being retrieved (but is kept).
    retrieval_floor: float = 8.0
    max_retrieved: int = 12
    #: How many raw events must agree before they may become a principle.
    min_events_per_principle: int = 2
    #: Ideas are never deleted — this only lowers their retrieval priority.
    idea_half_life_cycles: int = 12

    IMMORTAL_KINDS = (MemoryKind.CANON, MemoryKind.REJECTED, MemoryKind.SUCCESSFUL)

    def should_decay(self, record: MemoryRecord) -> bool:
        """Whether a record loses salience at the end of a cycle."""
        if record.kind in self.IMMORTAL_KINDS or record.is_principle:
            return False
        return True

    def decay(self, record: MemoryRecord) -> None:
        """Apply one cycle of decay in place."""
        if self.should_decay(record):
            record.decay(self.episodic_decay_per_cycle)

    def is_retrievable(self, record: MemoryRecord) -> bool:
        """Whether a record still surfaces during retrieval."""
        if record.is_principle or record.kind in self.IMMORTAL_KINDS:
            return True
        return record.salience >= self.retrieval_floor

    def may_become_principle(self, supporting_events: int) -> bool:
        """Guard against turning a single raw event into a rule."""
        return supporting_events >= self.min_events_per_principle

    def rank(self, records: list[MemoryRecord]) -> list[MemoryRecord]:
        """Order records for retrieval: principles first, then salience."""
        retrievable = [r for r in records if self.is_retrievable(r)]
        return sorted(
            retrievable,
            key=lambda r: (r.is_principle, r.salience, r.created_at),
            reverse=True,
        )[: self.max_retrieved]
