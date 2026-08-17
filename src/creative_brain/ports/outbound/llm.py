"""The LLM port.

Nothing in the domain or the application layer names a vendor. Swapping
Anthropic for OpenAI, a local model or the deterministic mock is an adapter
change and a line of configuration — never a code change above this line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable


class ModelRole(StrEnum):
    """Functional roles a model can be routed to.

    CREATOR, JUDGE and CRITIC are deliberately separate so the same model never
    grades its own homework (see ADR-003).
    """

    RESEARCH = "research"
    CREATIVE = "creative"
    CRITICISM = "criticism"
    JUDGING = "judging"
    STRUCTURING = "structuring"
    DREAMING = "dreaming"


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """One structured call to a language model."""

    task: str
    system: str
    user: str
    role: ModelRole = ModelRole.CREATIVE
    schema: Mapping[str, Any] | None = None
    temperature: float = 0.8
    max_tokens: int = 2048
    agent_id: str = ""
    correlation_id: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """A model's answer plus the accounting the engine needs for budgets."""

    text: str
    model: str
    data: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider: str = "unknown"

    @property
    def total_tokens(self) -> int:
        """Prompt plus completion tokens."""
        return self.input_tokens + self.output_tokens


@runtime_checkable
class LLMPort(Protocol):
    """What the creative mind needs from any language model."""

    @property
    def provider(self) -> str:
        """Provider name, used for logs and metrics."""
        ...

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one completion, returning structured data when a schema was given."""
        ...


@runtime_checkable
class BudgetPort(Protocol):
    """Read-only view of per-cycle LLM spend.

    The circadian clock needs to know how much the mind has spent this cycle,
    without knowing that a router — let alone which one — exists.
    """

    calls: int
    cost_usd: float

    def reset(self) -> None:
        """Start a new cycle's accounting."""
        ...


@runtime_checkable
class ModelRouterPort(Protocol):
    """Routes each functional role to a concrete model/provider."""

    def for_role(self, role: ModelRole) -> LLMPort:
        """The model assigned to a role."""
        ...

    def model_name(self, role: ModelRole) -> str:
        """The configured model id for a role."""
        ...
