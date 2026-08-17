"""Signals captured from the world, and the research that deepens them."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.domain.value_objects.identifiers import FindingId, ObservationId


class SignalDomain(StrEnum):
    """Where an observation came from."""

    SOCIETY = "society"
    TECHNOLOGY = "technology"
    ECONOMY = "economy"
    SCIENCE = "science"
    CULTURE = "culture"
    BEHAVIOUR = "behaviour"
    HUMAN_RELATIONS = "human_relations"
    INSTITUTIONS = "institutions"
    EVENTS = "events"
    SOCIAL_CHANGE = "social_change"


class SignalKind(StrEnum):
    """What kind of signal it is. Contradictions and oddities are the fuel."""

    FACT = "fact"
    TREND = "trend"
    ODDITY = "oddity"
    CONTRADICTION = "contradiction"
    WEAK_SIGNAL = "weak_signal"


@dataclass(slots=True)
class CreativeObservation:
    """Something noticed about the world. Never a story — only raw material."""

    id: ObservationId
    statement: str
    domain: SignalDomain
    kind: SignalKind
    captured_at: str
    cycle_id: str = ""
    source: str = "internal_observer"
    tension: str = ""
    tags: tuple[str, ...] = ()
    salience: float = 50.0

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "statement": self.statement,
            "domain": str(self.domain),
            "kind": str(self.kind),
            "captured_at": self.captured_at,
            "cycle_id": self.cycle_id,
            "source": self.source,
            "tension": self.tension,
            "tags": list(self.tags),
            "salience": self.salience,
        }


@dataclass(slots=True)
class ResearchFinding:
    """A deeper dive triggered by an observation the engine found interesting."""

    id: FindingId
    topic: str
    summary: str
    created_at: str
    cycle_id: str = ""
    observation_id: str = ""
    key_facts: tuple[str, ...] = ()
    implications: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    confidence: float = 50.0
    provider: str = "offline"
    tags: tuple[str, ...] = field(default=())

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "topic": self.topic,
            "summary": self.summary,
            "created_at": self.created_at,
            "cycle_id": self.cycle_id,
            "observation_id": self.observation_id,
            "key_facts": list(self.key_facts),
            "implications": list(self.implications),
            "sources": list(self.sources),
            "confidence": self.confidence,
            "provider": self.provider,
            "tags": list(self.tags),
        }
