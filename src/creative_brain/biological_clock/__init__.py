"""The BIOLOGICAL_CLOCK_AGENT.

This agent is deliberately **not** an LLM call. The rhythm of the mind is the
one thing that must stay deterministic, replayable and cheap: it runs on the
pure :class:`CircadianPolicy` in the domain, reading energy gauges, backlogs,
quality signals and budgets.

It owns WHEN. Every other agent owns WHAT, HOW and WHY.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from creative_brain.agents.definitions import AgentDefinition, default_definition
from creative_brain.domain.entities.circadian import (
    BiologicalPhase,
    CircadianDecision,
    CircadianState,
)
from creative_brain.domain.policies.circadian import CircadianPolicy
from creative_brain.ports.outbound.infrastructure import ClockPort, LoggerPort, MetricsPort


@dataclass
class BiologicalClockAgent:
    """Decides the next phase and how long it should last."""

    policy: CircadianPolicy
    clock: ClockPort
    logger: LoggerPort
    metrics: MetricsPort
    definition: AgentDefinition = field(default_factory=lambda: default_definition("BIOLOGICAL_CLOCK_AGENT"))
    last_decision: CircadianDecision | None = None

    @property
    def id(self) -> str:
        """Agent identifier."""
        return self.definition.id

    def decide(self, state: CircadianState) -> CircadianDecision:
        """Choose the next phase from the current state of the mind."""
        decision = self.policy.decide(state, now=self.clock.iso_now())
        self.last_decision = decision
        self.metrics.increment("circadian_decisions", phase=str(decision.phase))
        self.logger.info(
            "clock.decision",
            phase=str(decision.phase),
            reason=decision.reason,
            cycle_id=state.cycle_id,
            creative_energy=state.energy.creative.value,
            research_energy=state.energy.research.value,
            critical_energy=state.energy.critical.value,
        )
        return decision

    def phase_duration(self, phase: BiologicalPhase) -> float:
        """How long to dwell in a phase before deciding again.

        Zero in single-cycle and mock runs: the engine moves as fast as the work
        allows. In a long-running autonomous deployment this is what spreads a
        creative day across real hours.
        """
        return self.policy.phase_duration_seconds

    def report(self, state: CircadianState) -> dict[str, object]:
        """What ``creative-brain clock status`` renders."""
        return {
            "phase": str(state.phase),
            "cycle_number": state.cycle_number,
            "cycle_id": state.cycle_id,
            "phase_started_at": state.phase_started_at,
            "energy": state.energy.as_dict(),
            "phases_visited": list(state.phases_visited),
            "last_decision": self.last_decision.as_dict() if self.last_decision else None,
            "next_decision": "dynamic",
            "backlogs": {
                "observations": state.observation_backlog,
                "research": state.research_backlog,
                "seeds": state.seed_backlog,
                "concepts": state.concept_backlog,
                "unconsolidated_events": state.unconsolidated_events,
            },
            "budgets": {
                "llm_calls_this_cycle": state.llm_calls_this_cycle,
                "estimated_cost_usd": round(state.estimated_cost_usd, 6),
                "max_llm_calls_per_cycle": self.policy.max_llm_calls_per_cycle,
                "max_cost_usd_per_cycle": self.policy.max_cost_usd_per_cycle,
            },
        }


__all__ = ["BiologicalClockAgent"]
