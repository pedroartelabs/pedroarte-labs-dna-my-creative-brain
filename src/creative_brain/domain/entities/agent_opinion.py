"""What an agent thought about an idea, and why.

Opinions are evidence, not reasoning transcripts. We persist *decisions and the
structured grounds for them* — never a model's internal chain of thought.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.domain.value_objects.scores import ScoreBoard


class Verdict(StrEnum):
    """The stance an agent takes on an idea."""

    SUPPORT = "SUPPORT"
    REJECT = "REJECT"
    NEUTRAL = "NEUTRAL"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class AgentOpinion:
    """One agent's structured judgement of one artifact."""

    agent: str
    verdict: Verdict
    rationale: str
    created_at: str
    scores: ScoreBoard = field(default_factory=lambda: ScoreBoard({}))
    evidence: tuple[str, ...] = ()
    confidence: float = 50.0

    @property
    def is_blocking(self) -> bool:
        """A confident rejection blocks promotion regardless of the aggregate score."""
        return self.verdict is Verdict.REJECT and self.confidence >= 70.0

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "agent": self.agent,
            "verdict": str(self.verdict),
            "rationale": self.rationale,
            "created_at": self.created_at,
            "scores": self.scores.as_dict(),
            "evidence": list(self.evidence),
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """WHO decided WHAT, WHY, on which INPUTS, with which EVIDENCE, and WHEN."""

    who: str
    what: str
    why: str
    decided_at: str
    inputs: tuple[str, ...] = ()
    scores: dict[str, float] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    cycle_id: str = ""
    correlation_id: str = ""

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "who": self.who,
            "what": self.what,
            "why": self.why,
            "decided_at": self.decided_at,
            "inputs": list(self.inputs),
            "scores": dict(self.scores),
            "evidence": list(self.evidence),
            "cycle_id": self.cycle_id,
            "correlation_id": self.correlation_id,
        }
