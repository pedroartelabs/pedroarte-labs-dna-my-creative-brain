"""The agent runtime: prompt in, validated object out, health tracked.

Agents never call each other. They are invoked by use cases and orchestrators,
and they communicate through domain events and persisted artifacts. That is the
difference between a multi-agent society and agent spaghetti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from creative_brain.agents.definitions import AgentDefinition
from creative_brain.agents.schemas import json_schema_of
from creative_brain.domain.exceptions import AgentExecutionFailure, SchemaViolation
from creative_brain.ports.outbound.infrastructure import LoggerPort, MetricsPort
from creative_brain.ports.outbound.llm import LLMRequest, LLMResponse
from creative_brain.ports.outbound.prompts import PromptLibraryPort

TModel = TypeVar("TModel", bound=BaseModel)


@dataclass
class AgentHealth:
    """Tracks whether an agent is behaving. Read by the runtime health check."""

    agent_id: str
    calls: int = 0
    failures: int = 0
    schema_violations: int = 0
    empty_outputs: int = 0
    total_latency: float = 0.0
    last_error: str = ""

    @property
    def failure_rate(self) -> float:
        """Share of calls that failed, 0..1."""
        return round(self.failures / self.calls, 4) if self.calls else 0.0

    @property
    def average_latency(self) -> float:
        """Mean seconds per call."""
        return round(self.total_latency / self.calls, 4) if self.calls else 0.0

    @property
    def is_unhealthy(self) -> bool:
        """Repeated failures, schema violations or empty answers mark an agent as broken."""
        if self.calls < 3:
            return False
        return self.failure_rate > 0.5 or self.schema_violations >= 3 or self.empty_outputs >= 3

    def as_dict(self) -> dict[str, Any]:
        """Serialisation-friendly view."""
        return {
            "agent_id": self.agent_id,
            "calls": self.calls,
            "failures": self.failures,
            "schema_violations": self.schema_violations,
            "empty_outputs": self.empty_outputs,
            "failure_rate": self.failure_rate,
            "average_latency": self.average_latency,
            "unhealthy": self.is_unhealthy,
            "last_error": self.last_error,
        }


@dataclass
class AgentContext:
    """Everything an agent needs that is not its own prompt."""

    prompts: PromptLibraryPort
    complete: Any  # ModelRouter.complete — a Callable[[LLMRequest], LLMResponse]
    logger: LoggerPort
    metrics: MetricsPort
    correlation_id: str = ""
    cycle_id: str = ""
    now: str = ""


@dataclass
class Agent(Generic[TModel]):
    """One member of the society.

    Failures are contained: an agent that cannot produce a valid answer returns
    a ``fallback`` (when one is provided) so a single broken agent cannot stop
    a whole creative cycle.
    """

    definition: AgentDefinition
    output_model: type[TModel]
    context: AgentContext
    health: AgentHealth = field(init=False)

    def __post_init__(self) -> None:
        self.health = AgentHealth(agent_id=self.definition.id)

    @property
    def id(self) -> str:
        """The agent's identifier."""
        return self.definition.id

    def run(
        self,
        *,
        variables: dict[str, str] | None = None,
        hints: dict[str, str] | None = None,
        fallback: TModel | None = None,
    ) -> TModel:
        """Render the prompt, call the model, validate the answer."""
        variables = variables or {}
        started = 0.0
        self.health.calls += 1
        try:
            system, user = self.context.prompts.render(self.definition.prompt, **variables)
        except Exception as exc:  # noqa: BLE001 - missing prompt is a configuration failure
            return self._fail(f"prompt '{self.definition.prompt}' unavailable: {exc}", fallback)

        request = LLMRequest(
            task=self.definition.task,
            system=system,
            user=user,
            role=self.definition.model_role,
            schema=json_schema_of(self.output_model),
            temperature=self.definition.temperature,
            agent_id=self.definition.id,
            correlation_id=self.context.correlation_id,
            metadata={**(hints or {}), "cycle_id": self.context.cycle_id},
        )

        try:
            response: LLMResponse = self.context.complete(request)
        except Exception as exc:  # noqa: BLE001 - contained so one agent cannot stop the cycle
            return self._fail(str(exc), fallback)

        self.health.total_latency += started
        if response.data is None:
            self.health.empty_outputs += 1
            return self._fail("model returned no structured data", fallback)

        try:
            parsed = self.output_model.model_validate(response.data)
        except ValidationError as exc:
            self.health.schema_violations += 1
            self.context.metrics.increment("agent_schema_violations", agent=self.definition.id)
            if fallback is not None:
                self.context.logger.warning(
                    "agent.schema_violation", agent=self.definition.id, error=str(exc)[:400]
                )
                return fallback
            raise SchemaViolation(self.definition.id, str(exc)[:400]) from exc

        self.context.metrics.increment("agent_calls", agent=self.definition.id)
        self.context.logger.debug(
            "agent.ok", agent=self.definition.id, task=self.definition.task
        )
        return parsed

    def _fail(self, reason: str, fallback: TModel | None) -> TModel:
        self.health.failures += 1
        self.health.last_error = reason[:400]
        self.context.metrics.increment("agent_failures", agent=self.definition.id)
        self.context.logger.warning("agent.failed", agent=self.definition.id, error=reason[:400])
        if fallback is not None:
            return fallback
        raise AgentExecutionFailure(self.definition.id, reason)


__all__ = ["Agent", "AgentContext", "AgentHealth"]
