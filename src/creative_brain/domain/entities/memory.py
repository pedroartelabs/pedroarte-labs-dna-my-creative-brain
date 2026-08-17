"""Memory records, obsessions and dreams.

The engine distinguishes a RAW EVENT from a LEARNED PRINCIPLE. Episodic memory
stores what happened; semantic memory stores what it means. Only the second
kind is allowed to change how the engine behaves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.domain.value_objects.identifiers import DreamId, MemoryId


class MemoryKind(StrEnum):
    """The memory subsystems."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    CREATIVE = "creative"
    REJECTED = "rejected"
    SUCCESSFUL = "successful"
    CANON = "canon"
    EXPERIMENTAL = "experimental"


@dataclass(slots=True)
class MemoryRecord:
    """One remembered thing, typed by which memory it belongs to."""

    id: MemoryId
    kind: MemoryKind
    summary: str
    created_at: str
    cycle_id: str = ""
    subject_id: str = ""
    detail: str = ""
    tags: tuple[str, ...] = ()
    salience: float = 50.0
    is_principle: bool = False
    source_events: tuple[str, ...] = ()

    @property
    def is_raw_event(self) -> bool:
        """Episodic records are raw history and must never be treated as a lesson."""
        return self.kind is MemoryKind.EPISODIC and not self.is_principle

    def decay(self, factor: float) -> None:
        """Lower salience over time. Records are never deleted, only de-prioritised."""
        self.salience = max(0.0, round(self.salience * max(0.0, min(1.0, factor)), 4))

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "kind": str(self.kind),
            "summary": self.summary,
            "detail": self.detail,
            "created_at": self.created_at,
            "cycle_id": self.cycle_id,
            "subject_id": self.subject_id,
            "tags": list(self.tags),
            "salience": self.salience,
            "is_principle": self.is_principle,
            "source_events": list(self.source_events),
        }


@dataclass(slots=True)
class Obsession:
    """A theme that keeps coming back.

    An obsession explored from a new angle is a signature. The same premise
    wearing a new costume is repetition — the engine must tell them apart.
    """

    theme: str
    occurrences: int = 0
    distinct_angles: tuple[str, ...] = ()
    first_seen_at: str = ""
    last_seen_at: str = ""
    saturation: float = 0.0

    def observe(self, angle: str, at: str) -> None:
        """Register one more appearance, tracking whether the angle is new."""
        self.occurrences += 1
        normalised = angle.strip().lower()
        if normalised and normalised not in {a.lower() for a in self.distinct_angles}:
            self.distinct_angles = (*self.distinct_angles, angle.strip())
        self.first_seen_at = self.first_seen_at or at
        self.last_seen_at = at
        self.saturation = self._saturation()

    def _saturation(self) -> float:
        """High when the theme repeats without producing new angles."""
        if self.occurrences <= 1:
            return 0.0
        angle_ratio = len(self.distinct_angles) / self.occurrences
        volume = min(1.0, self.occurrences / 12.0)
        return round(max(0.0, min(100.0, (1.0 - angle_ratio) * volume * 100.0)), 2)

    @property
    def is_repetition(self) -> bool:
        """Whether this looks like disguised repetition rather than a real obsession."""
        return self.saturation >= 60.0

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "theme": self.theme,
            "occurrences": self.occurrences,
            "distinct_angles": list(self.distinct_angles),
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "saturation": self.saturation,
            "is_repetition": self.is_repetition,
        }


@dataclass(slots=True)
class Dream:
    """A DREAMING-phase session: free association with plausibility switched off."""

    id: DreamId
    started_at: str
    cycle_id: str = ""
    finished_at: str = ""
    fragments: tuple[str, ...] = ()
    resurrected_ids: tuple[str, ...] = ()
    harvested_seed_ids: tuple[str, ...] = ()
    strangeness: float = 0.0
    notes: str = ""
    _unused: tuple[str, ...] = field(default=(), repr=False)

    def add_fragment(self, fragment: str) -> None:
        """Record one dream fragment. Nothing is judged during the dream itself."""
        if fragment.strip():
            self.fragments = (*self.fragments, fragment.strip())

    def finish(self, *, at: str, harvested: tuple[str, ...], strangeness: float) -> None:
        """Close the dream and record what the waking mind salvaged from it."""
        self.finished_at = at
        self.harvested_seed_ids = harvested
        self.strangeness = round(max(0.0, min(100.0, strangeness)), 2)

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "fragments": list(self.fragments),
            "resurrected_ids": list(self.resurrected_ids),
            "harvested_seed_ids": list(self.harvested_seed_ids),
            "strangeness": self.strangeness,
            "notes": self.notes,
        }
