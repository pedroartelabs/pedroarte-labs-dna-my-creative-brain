"""The circadian decision policy — the brain's sense of WHEN.

This is deliberately **not** a cron table. The policy reads the current state
(energy gauges, backlogs, quality signals, budgets) and picks the phase that
best serves the mind right now. It is a pure function, so it is fully testable
without a real clock.
"""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.domain.entities.circadian import (
    PHASE_COST,
    PHASE_ORDER,
    BiologicalPhase,
    CircadianDecision,
    CircadianState,
)
from creative_brain.domain.exceptions import ClockDecisionFailure
from creative_brain.domain.value_objects.energy import EnergyKind


@dataclass(frozen=True, slots=True)
class CircadianPolicy:
    """Thresholds that shape the rhythm. Every value comes from configuration."""

    creative_floor: float = 25.0
    research_floor: float = 20.0
    critical_floor: float = 20.0
    memory_pressure_ceiling: float = 70.0
    novelty_pressure_ceiling: float = 65.0
    novelty_floor: float = 40.0
    duplicate_rate_ceiling: float = 0.35
    failure_rate_ceiling: float = 0.30
    min_observations_before_creating: int = 3
    min_seeds_before_tournament: int = 4
    max_llm_calls_per_cycle: int = 400
    max_cost_usd_per_cycle: float = 5.0
    dream_mode_enabled: bool = True
    exploration_enabled: bool = True
    second_wind_enabled: bool = True
    phase_duration_seconds: float = 0.0

    def decide(self, state: CircadianState, *, now: str) -> CircadianDecision:
        """Choose the next phase from the current state."""
        signals = self._signals(state)

        for rule in (
            self._rule_budget_exhausted,
            self._rule_must_awaken,
            self._rule_memory_pressure,
            self._rule_exhausted,
            self._rule_needs_observation,
            self._rule_needs_research,
            self._rule_digest_before_creating,
            self._rule_ready_to_create,
            self._rule_needs_reflection,
            self._rule_second_wind,
            self._rule_exploration,
            self._rule_consolidate,
            self._rule_dream,
        ):
            outcome = rule(state)
            if outcome is not None:
                phase, reason = outcome
                return self._decision(phase, reason, now, signals)

        phase, reason = self._fallback(state)
        return self._decision(phase, reason, now, signals)

    # ------------------------------------------------------------------ rules

    def _rule_budget_exhausted(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        over_calls = state.llm_calls_this_cycle >= self.max_llm_calls_per_cycle
        over_cost = state.estimated_cost_usd >= self.max_cost_usd_per_cycle
        if (over_calls or over_cost) and not state.visited(BiologicalPhase.CONSOLIDATION):
            return BiologicalPhase.CONSOLIDATION, "cycle budget exhausted; consolidate and sleep"
        if over_calls or over_cost:
            return BiologicalPhase.DEEP_SLEEP, "cycle budget exhausted"
        return None

    def _rule_must_awaken(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if state.phase is BiologicalPhase.DEEP_SLEEP or not state.phases_visited:
            return BiologicalPhase.AWAKENING, "cycle boundary: reload context and restore state"
        return None

    def _rule_memory_pressure(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        pressure = state.energy.get(EnergyKind.MEMORY_PRESSURE).value
        if pressure >= self.memory_pressure_ceiling and not state.visited(
            BiologicalPhase.CONSOLIDATION
        ):
            return (
                BiologicalPhase.CONSOLIDATION,
                f"memory pressure {pressure:.0f} above ceiling {self.memory_pressure_ceiling:.0f}",
            )
        return None

    def _rule_exhausted(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        creative = state.energy.get(EnergyKind.CREATIVE).value
        critical = state.energy.get(EnergyKind.CRITICAL).value
        research = state.energy.get(EnergyKind.RESEARCH).value
        if creative < self.creative_floor and critical < self.critical_floor and research < 30:
            if not state.visited(BiologicalPhase.CONSOLIDATION):
                return BiologicalPhase.CONSOLIDATION, "all gauges low; consolidate before sleeping"
            if self.dream_mode_enabled and not state.visited(BiologicalPhase.DREAMING):
                return BiologicalPhase.DREAMING, "gauges low; dreaming costs little and pays later"
            return BiologicalPhase.DEEP_SLEEP, "all gauges low; rest"
        return None

    def _rule_needs_observation(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if state.visited(BiologicalPhase.OBSERVATION):
            return None
        if state.energy.get(EnergyKind.RESEARCH).value < self.research_floor:
            return None
        return BiologicalPhase.OBSERVATION, "no observations captured yet in this cycle"

    def _rule_needs_research(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if state.visited(BiologicalPhase.HUNT):
            return None
        if state.energy.get(EnergyKind.RESEARCH).value < self.research_floor:
            return None
        if state.observation_backlog <= 0:
            return None
        return (
            BiologicalPhase.HUNT,
            f"{state.observation_backlog} observations waiting to be hunted down",
        )

    def _rule_digest_before_creating(
        self, state: CircadianState
    ) -> tuple[BiologicalPhase, str] | None:
        """Never create straight after a large information intake."""
        intake = state.observation_backlog + state.research_backlog
        if (
            intake >= 8
            and state.visited(BiologicalPhase.HUNT)
            and not state.visited(BiologicalPhase.DIGESTION)
        ):
            return BiologicalPhase.DIGESTION, f"large intake ({intake}); digest before creating"
        return None

    def _rule_ready_to_create(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if state.visited(BiologicalPhase.CREATION):
            return None
        if state.energy.get(EnergyKind.CREATIVE).value < self.creative_floor:
            return None
        if not state.visited(BiologicalPhase.FOCUS):
            if state.observation_backlog + state.research_backlog >= (
                self.min_observations_before_creating
            ):
                return BiologicalPhase.FOCUS, "enough raw material; narrow down before creating"
            return None
        return BiologicalPhase.CREATION, "focus set and creative energy available"

    def _rule_needs_reflection(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if not state.visited(BiologicalPhase.CREATION):
            return None
        if state.visited(BiologicalPhase.REFLECTION):
            return None
        if state.energy.get(EnergyKind.CRITICAL).value < self.critical_floor:
            return None
        return BiologicalPhase.REFLECTION, "fresh output needs to meet existing memory"

    def _rule_second_wind(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if not self.second_wind_enabled or state.visited(BiologicalPhase.SECOND_WIND):
            return None
        if not state.visited(BiologicalPhase.REFLECTION):
            return None
        weak = state.recent_quality < 55.0 or state.seed_backlog < self.min_seeds_before_tournament
        if weak and state.energy.get(EnergyKind.CREATIVE).value >= self.creative_floor:
            return BiologicalPhase.SECOND_WIND, "first pass was thin; revisit rejected material"
        return None

    def _rule_exploration(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if not self.exploration_enabled or state.visited(BiologicalPhase.EXPLORATION):
            return None
        if not state.visited(BiologicalPhase.REFLECTION):
            return None
        novelty_pressure = state.energy.get(EnergyKind.NOVELTY_PRESSURE).value
        too_similar = (
            state.recent_novelty < self.novelty_floor
            or state.duplicate_rate > self.duplicate_rate_ceiling
            or novelty_pressure > self.novelty_pressure_ceiling
        )
        if too_similar and state.energy.get(EnergyKind.CREATIVE).value >= self.creative_floor:
            return (
                BiologicalPhase.EXPLORATION,
                f"novelty {state.recent_novelty:.0f} / duplicates {state.duplicate_rate:.2f}: "
                "push away from the DNA",
            )
        return None

    def _rule_consolidate(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if state.visited(BiologicalPhase.CONSOLIDATION):
            return None
        if not state.visited(BiologicalPhase.REFLECTION):
            return None
        return BiologicalPhase.CONSOLIDATION, "cycle output ready to become memory"

    def _rule_dream(self, state: CircadianState) -> tuple[BiologicalPhase, str] | None:
        if not self.dream_mode_enabled or state.visited(BiologicalPhase.DREAMING):
            return None
        if not state.visited(BiologicalPhase.CONSOLIDATION):
            return None
        return BiologicalPhase.DREAMING, "memory consolidated; free association is now cheap"

    # --------------------------------------------------------------- fallback

    def _fallback(self, state: CircadianState) -> tuple[BiologicalPhase, str]:
        """Move forward through the canonical day.

        A day only runs forwards: phases that were skipped because their
        trigger never fired (DIGESTION with no intake, EXPLORATION with healthy
        novelty) are *not* back-filled after DREAMING. Missing them is the
        correct outcome, not a gap to patch.

        The fallback also respects the energy floors. Without that it could
        hand back a phase that an explicit rule had just declined for lack of
        energy — which would make the floors decorative.
        """
        position = PHASE_ORDER.index(state.phase) if state.phase in PHASE_ORDER else -1
        for phase in PHASE_ORDER[position + 1 :]:
            if state.visited(phase):
                continue
            if not self._can_afford(phase, state):
                continue
            return phase, "canonical rhythm"
        if not state.visited(BiologicalPhase.CONSOLIDATION):
            return BiologicalPhase.CONSOLIDATION, "nothing affordable left; consolidate the cycle"
        return BiologicalPhase.DEEP_SLEEP, "every phase of this cycle is complete"

    def _can_afford(self, phase: BiologicalPhase, state: CircadianState) -> bool:
        """Whether the gauge a phase draws on is above its configured floor."""
        kind, cost = PHASE_COST[phase]
        if cost <= 0:
            return True
        floor = {
            EnergyKind.CREATIVE: self.creative_floor,
            EnergyKind.RESEARCH: self.research_floor,
            EnergyKind.CRITICAL: self.critical_floor,
        }.get(kind, 0.0)
        return state.energy.get(kind).value >= floor

    # ---------------------------------------------------------------- helpers

    def _signals(self, state: CircadianState) -> dict[str, float]:
        return {
            **state.energy.as_dict(),
            "observation_backlog": float(state.observation_backlog),
            "research_backlog": float(state.research_backlog),
            "seed_backlog": float(state.seed_backlog),
            "concept_backlog": float(state.concept_backlog),
            "recent_novelty": state.recent_novelty,
            "recent_quality": state.recent_quality,
            "duplicate_rate": state.duplicate_rate,
            "failure_rate": state.failure_rate,
            "llm_calls_this_cycle": float(state.llm_calls_this_cycle),
            "estimated_cost_usd": state.estimated_cost_usd,
        }

    def _decision(
        self,
        phase: BiologicalPhase,
        reason: str,
        now: str,
        signals: dict[str, float],
    ) -> CircadianDecision:
        if not now:
            raise ClockDecisionFailure("circadian decisions require a timestamp")
        return CircadianDecision(
            phase=phase,
            reason=reason,
            decided_at=now,
            duration_seconds=self.phase_duration_seconds,
            signals=signals,
            ends_cycle=phase is BiologicalPhase.DEEP_SLEEP,
        )
