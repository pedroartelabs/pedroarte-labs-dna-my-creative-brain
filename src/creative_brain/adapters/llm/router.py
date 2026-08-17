"""Model routing, budgeting and instrumentation.

Two things happen here that matter to the *creative* result, not just to ops:

* **role separation** — CREATOR, CRITIC and JUDGE can be routed to different
  models so the engine never grades its own homework;
* **budget enforcement** — the circadian clock reads call counts and spend, so
  a runaway cycle slows itself down instead of running up a bill.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from creative_brain.adapters.resilience import CircuitBreaker, CircuitOpen, RateLimiter, RetryPolicy
from creative_brain.domain.exceptions import BudgetExceeded
from creative_brain.ports.outbound.infrastructure import ClockPort, LoggerPort, MetricsPort
from creative_brain.ports.outbound.llm import LLMPort, LLMRequest, LLMResponse, ModelRole


@dataclass
class CallBudget:
    """Per-cycle ceilings the router refuses to cross."""

    max_calls_per_cycle: int = 400
    max_cost_usd_per_cycle: float = 5.0
    calls: int = 0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    def reset(self) -> None:
        """Start a new cycle's accounting."""
        self.calls = 0
        self.cost_usd = 0.0
        self.tokens_in = 0
        self.tokens_out = 0

    def check(self) -> None:
        """Raise before spending anything more than allowed."""
        if self.calls >= self.max_calls_per_cycle:
            raise BudgetExceeded(
                f"LLM call budget exhausted: {self.calls}/{self.max_calls_per_cycle} this cycle"
            )
        if self.cost_usd >= self.max_cost_usd_per_cycle:
            raise BudgetExceeded(
                f"LLM cost budget exhausted: ${self.cost_usd:.4f} of "
                f"${self.max_cost_usd_per_cycle:.2f} this cycle"
            )

    def record(self, response: LLMResponse) -> None:
        """Account for one completed call."""
        self.calls += 1
        self.cost_usd += response.estimated_cost_usd
        self.tokens_in += response.input_tokens
        self.tokens_out += response.output_tokens

    def as_dict(self) -> dict[str, float]:
        """Serialisation-friendly view."""
        return {
            "calls": float(self.calls),
            "cost_usd": round(self.cost_usd, 6),
            "tokens_in": float(self.tokens_in),
            "tokens_out": float(self.tokens_out),
        }


@dataclass
class ModelRouter:
    """Routes each role to a provider and wraps every call in the ops concerns."""

    providers: dict[ModelRole, LLMPort]
    default: LLMPort
    clock: ClockPort
    metrics: MetricsPort | None = None
    logger: LoggerPort | None = None
    budget: CallBudget = field(default_factory=CallBudget)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    rate_limiter: RateLimiter = field(default_factory=lambda: RateLimiter(max_calls=120))
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    model_names: dict[ModelRole, str] = field(default_factory=dict)

    def for_role(self, role: ModelRole) -> LLMPort:
        """The provider assigned to a role."""
        return self.providers.get(role, self.default)

    def model_name(self, role: ModelRole) -> str:
        """The configured model id for a role."""
        return self.model_names.get(role, getattr(self.for_role(role), "provider", "unknown"))

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one request under budget, rate limit, retry and circuit breaker.

        LLM completions are read-only with respect to our own state, so they are
        safe to retry — unlike, say, writing a project to disk.
        """
        self.budget.check()
        if not self.breaker.allow(clock=self.clock):
            raise CircuitOpen(f"LLM circuit open; refusing '{request.task}'")
        self.rate_limiter.acquire(clock=self.clock)

        provider = self.for_role(request.role)
        started = self.clock.now().timestamp()
        try:
            response = self.retry.run(
                lambda: provider.complete(request),
                clock=self.clock,
                idempotent=True,
                on_retry=self._on_retry(request),
            )
        except Exception:
            self.breaker.record_failure(clock=self.clock)
            if self.metrics:
                self.metrics.increment("llm_calls_failed_total", role=str(request.role))
            raise

        self.breaker.record_success()
        self.budget.record(response)
        if self.metrics:
            self.metrics.increment("llm_calls", role=str(request.role), provider=response.provider)
            self.metrics.increment("token_usage", float(response.total_tokens))
            self.metrics.increment("estimated_llm_cost_usd", response.estimated_cost_usd)
            self.metrics.observe(
                "llm_latency_seconds", max(0.0, self.clock.now().timestamp() - started)
            )
        if self.logger:
            self.logger.debug(
                "llm.call",
                task=request.task,
                role=str(request.role),
                agent_id=request.agent_id,
                provider=response.provider,
                model=response.model,
                tokens=response.total_tokens,
                cost_usd=response.estimated_cost_usd,
            )
        return response

    def _on_retry(self, request: LLMRequest):  # noqa: ANN202 - closure returned to RetryPolicy
        def hook(attempt: int, error: Exception) -> None:
            if self.logger:
                self.logger.warning(
                    "llm.retry", task=request.task, attempt=attempt, error=str(error)
                )
            if self.metrics:
                self.metrics.increment("llm_retries_total", role=str(request.role))

        return hook


__all__ = ["CallBudget", "ModelRouter"]
