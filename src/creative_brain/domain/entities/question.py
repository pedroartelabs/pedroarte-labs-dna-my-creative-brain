"""Creative questions and the seeds they germinate into."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import QuestionId, SeedId


@dataclass(slots=True)
class CreativeQuestion:
    """A question the engine decided is worth asking.

    Article 9: every work needs a central question. Questions are first-class
    citizens here — they outlive the ideas that failed to answer them.
    """

    id: QuestionId
    text: str
    created_at: str
    cycle_id: str = ""
    observation_id: str = ""
    provocation: str = ""
    depth: int = 1
    tags: tuple[str, ...] = ()
    answered_by: tuple[str, ...] = ()

    def deepen(self, text: str, question_id: QuestionId, at: str) -> CreativeQuestion:
        """Produce a follow-up question one level deeper than this one."""
        return CreativeQuestion(
            id=question_id,
            text=text,
            created_at=at,
            cycle_id=self.cycle_id,
            observation_id=self.observation_id,
            provocation=self.text,
            depth=self.depth + 1,
            tags=self.tags,
        )

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "text": self.text,
            "created_at": self.created_at,
            "cycle_id": self.cycle_id,
            "observation_id": self.observation_id,
            "provocation": self.provocation,
            "depth": self.depth,
            "tags": list(self.tags),
            "answered_by": list(self.answered_by),
        }


@dataclass(slots=True)
class CreativeSeed:
    """The smallest unit of creative intent: one sentence with a mechanism behind it."""

    id: SeedId
    statement: str
    created_at: str
    origin: GenomeOrigin
    cycle_id: str = ""
    question_id: str = ""
    observation_id: str = ""
    tags: tuple[str, ...] = ()
    heat: float = 50.0

    @property
    def mechanism(self) -> OriginMechanism:
        """Which cognitive mechanism produced this seed."""
        return self.origin.mechanism

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "statement": self.statement,
            "created_at": self.created_at,
            "origin": self.origin.as_dict(),
            "cycle_id": self.cycle_id,
            "question_id": self.question_id,
            "observation_id": self.observation_id,
            "tags": list(self.tags),
            "heat": self.heat,
        }
