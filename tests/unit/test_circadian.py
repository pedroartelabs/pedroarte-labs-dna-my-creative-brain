"""The biological clock: the mind's sense of WHEN.

Every test here drives a pure policy with an explicit state, so the rhythm is
verified without a real clock, a real model or a real cycle.
"""

from __future__ import annotations

import pytest

from creative_brain.domain.entities.circadian import (
    PHASE_ORDER,
    BiologicalPhase,
    CircadianState,
)
from creative_brain.domain.exceptions import ClockDecisionFailure
from creative_brain.domain.policies.circadian import CircadianPolicy
from creative_brain.domain.value_objects.energy import EnergyLevel, EnergyProfile

NOW = "2026-01-01T06:00:00Z"


def state_after(*phases: BiologicalPhase, **fields) -> CircadianState:
    """A state that has already executed ``phases`` in the current cycle."""
    state = CircadianState(cycle_id="cycle_test0001", cycle_number=1)
    state.phase = phases[-1] if phases else BiologicalPhase.AWAKENING
    state.phases_visited = tuple(str(p) for p in phases)
    for key, value in fields.items():
        setattr(state, key, value)
    return state


class TestCircadianDecision:
    def test_a_cold_start_always_awakens(self):
        decision = CircadianPolicy().decide(CircadianState(), now=NOW)
        assert decision.phase is BiologicalPhase.AWAKENING

    def test_a_timestamp_is_mandatory(self):
        with pytest.raises(ClockDecisionFailure):
            CircadianPolicy().decide(CircadianState(), now="")

    def test_deep_sleep_ends_the_cycle(self):
        """With every other phase done, the only thing left is to sleep."""
        state = state_after(*PHASE_ORDER[:-1])
        decision = CircadianPolicy().decide(state, now=NOW)
        assert decision.phase is BiologicalPhase.DEEP_SLEEP
        assert decision.ends_cycle

    def test_waking_follows_deep_sleep(self):
        """DEEP_SLEEP is a cycle boundary, not a dead end."""
        state = state_after(*PHASE_ORDER)
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.AWAKENING

    def test_a_decision_carries_its_signals(self):
        decision = CircadianPolicy().decide(state_after(BiologicalPhase.AWAKENING), now=NOW)
        assert "creative_energy" in decision.signals
        assert decision.reason


class TestPhaseSelectionRules:
    def test_observation_comes_first_after_waking(self):
        decision = CircadianPolicy().decide(state_after(BiologicalPhase.AWAKENING), now=NOW)
        assert decision.phase is BiologicalPhase.OBSERVATION

    def test_hunt_follows_a_backlog_of_observations(self):
        state = state_after(
            BiologicalPhase.AWAKENING, BiologicalPhase.OBSERVATION, observation_backlog=6
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.HUNT

    def test_a_large_intake_forces_digestion_before_creating(self):
        """Never create immediately after a large amount of information."""
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.HUNT,
            observation_backlog=8,
            research_backlog=4,
        )
        decision = CircadianPolicy().decide(state, now=NOW)
        assert decision.phase is BiologicalPhase.DIGESTION

    def test_a_small_intake_goes_straight_to_focus(self):
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.HUNT,
            observation_backlog=4,
            research_backlog=1,
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.FOCUS

    def test_creation_requires_focus_first(self):
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.HUNT,
            observation_backlog=4,
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.FOCUS

    def test_creation_follows_focus(self):
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.HUNT,
            BiologicalPhase.FOCUS,
            observation_backlog=4,
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.CREATION

    def test_reflection_follows_creation(self):
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.FOCUS,
            BiologicalPhase.CREATION,
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.REFLECTION


class TestEnergyDrivenRules:
    def test_low_creative_energy_blocks_creation(self):
        """An empty creative gauge must not be overridden by the canonical order."""
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.HUNT,
            BiologicalPhase.FOCUS,
            observation_backlog=6,
        )
        state.energy = EnergyProfile(creative=EnergyLevel(10))
        assert CircadianPolicy().decide(state, now=NOW).phase is not BiologicalPhase.CREATION

    def test_exhaustion_routes_to_consolidation_then_rest(self):
        flat = EnergyProfile(
            creative=EnergyLevel(5), research=EnergyLevel(5), critical=EnergyLevel(5)
        )
        state = state_after(BiologicalPhase.AWAKENING, BiologicalPhase.CREATION)
        state.energy = flat
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.CONSOLIDATION

        state = state_after(
            BiologicalPhase.AWAKENING, BiologicalPhase.CREATION, BiologicalPhase.CONSOLIDATION
        )
        state.energy = flat
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.DREAMING

    def test_exhaustion_sleeps_when_dreaming_is_disabled(self):
        state = state_after(
            BiologicalPhase.AWAKENING, BiologicalPhase.CREATION, BiologicalPhase.CONSOLIDATION
        )
        state.energy = EnergyProfile(
            creative=EnergyLevel(5), research=EnergyLevel(5), critical=EnergyLevel(5)
        )
        policy = CircadianPolicy(dream_mode_enabled=False)
        assert policy.decide(state, now=NOW).phase is BiologicalPhase.DEEP_SLEEP

    def test_memory_pressure_preempts_everything(self):
        state = state_after(BiologicalPhase.AWAKENING, BiologicalPhase.OBSERVATION)
        state.energy = EnergyProfile(memory_pressure=EnergyLevel(95))
        decision = CircadianPolicy().decide(state, now=NOW)
        assert decision.phase is BiologicalPhase.CONSOLIDATION
        assert "memory pressure" in decision.reason


class TestQualityDrivenRules:
    #: A state that has realistically reached REFLECTION already went through
    #: the perception phases; the policy would otherwise send it back to them.
    AFTER_REFLECTION = (
        BiologicalPhase.AWAKENING,
        BiologicalPhase.OBSERVATION,
        BiologicalPhase.HUNT,
        BiologicalPhase.FOCUS,
        BiologicalPhase.CREATION,
        BiologicalPhase.REFLECTION,
    )

    def test_low_novelty_pushes_the_mind_into_exploration(self):
        state = state_after(
            *self.AFTER_REFLECTION,
            BiologicalPhase.SECOND_WIND,
            recent_novelty=20.0,
            recent_quality=80.0,
            seed_backlog=20,
        )
        decision = CircadianPolicy().decide(state, now=NOW)
        assert decision.phase is BiologicalPhase.EXPLORATION
        assert "novelty" in decision.reason

    def test_a_thin_first_pass_triggers_a_second_wind(self):
        state = state_after(
            *self.AFTER_REFLECTION,
            recent_quality=30.0,
            recent_novelty=80.0,
            seed_backlog=1,
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.SECOND_WIND

    def test_healthy_output_skips_the_corrective_phases(self):
        state = state_after(
            *self.AFTER_REFLECTION,
            recent_quality=90.0,
            recent_novelty=90.0,
            seed_backlog=40,
            duplicate_rate=0.0,
        )
        assert CircadianPolicy().decide(state, now=NOW).phase is BiologicalPhase.CONSOLIDATION


class TestBudgetRules:
    def test_call_budget_exhaustion_ends_the_day(self):
        state = state_after(
            BiologicalPhase.AWAKENING, BiologicalPhase.CREATION, llm_calls_this_cycle=500
        )
        decision = CircadianPolicy(max_llm_calls_per_cycle=400).decide(state, now=NOW)
        assert decision.phase is BiologicalPhase.CONSOLIDATION

        spent = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.CREATION,
            BiologicalPhase.CONSOLIDATION,
            llm_calls_this_cycle=500,
        )
        after = CircadianPolicy(max_llm_calls_per_cycle=400).decide(spent, now=NOW)
        assert after.phase is BiologicalPhase.DEEP_SLEEP

    def test_cost_budget_exhaustion_ends_the_day(self):
        state = state_after(
            BiologicalPhase.AWAKENING,
            BiologicalPhase.CREATION,
            BiologicalPhase.CONSOLIDATION,
            estimated_cost_usd=99.0,
        )
        decision = CircadianPolicy(max_cost_usd_per_cycle=5.0).decide(state, now=NOW)
        assert decision.phase is BiologicalPhase.DEEP_SLEEP


class TestRhythmProperties:
    def test_a_full_day_terminates_and_visits_the_core_phases(self):
        """The rhythm must always converge on DEEP_SLEEP, never loop forever."""
        policy = CircadianPolicy()
        state = CircadianState()
        state.begin_cycle(cycle_id="cycle_test0001", at=NOW)
        visited: list[BiologicalPhase] = []
        for _ in range(40):
            decision = policy.decide(state, now=NOW)
            state.enter(decision)
            visited.append(decision.phase)
            if decision.ends_cycle:
                break
        assert visited[0] is BiologicalPhase.AWAKENING
        assert visited[-1] is BiologicalPhase.DEEP_SLEEP
        for required in (
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.CREATION,
            BiologicalPhase.REFLECTION,
            BiologicalPhase.CONSOLIDATION,
        ):
            assert required in visited

    def test_no_phase_repeats_within_a_cycle(self):
        policy = CircadianPolicy()
        state = CircadianState()
        state.begin_cycle(cycle_id="cycle_test0001", at=NOW)
        seen: list[BiologicalPhase] = []
        for _ in range(40):
            decision = policy.decide(state, now=NOW)
            state.enter(decision)
            seen.append(decision.phase)
            if decision.ends_cycle:
                break
        assert len(seen) == len(set(seen))

    def test_the_day_only_moves_forward(self):
        """Optional phases that were skipped are not back-filled after DREAMING."""
        policy = CircadianPolicy()
        state = CircadianState()
        state.begin_cycle(cycle_id="cycle_test0001", at=NOW)
        order: list[int] = []
        for _ in range(40):
            decision = policy.decide(state, now=NOW)
            state.enter(decision)
            order.append(PHASE_ORDER.index(decision.phase))
            if decision.ends_cycle:
                break
        # Corrective rules may pull a phase forward, but DREAMING is never
        # followed by anything other than DEEP_SLEEP.
        dreaming = PHASE_ORDER.index(BiologicalPhase.DREAMING)
        if dreaming in order:
            after = order[order.index(dreaming) + 1 :]
            assert all(index > dreaming for index in after)


class TestCircadianState:
    def test_entering_a_phase_spends_its_gauge(self):
        state = CircadianState()
        before = state.energy.creative.value
        decision = CircadianPolicy().decide(state, now=NOW)
        state.enter(decision)
        assert state.energy.creative.value < before

    def test_ending_a_cycle_restores_through_sleep(self):
        state = CircadianState()
        state.energy = EnergyProfile(creative=EnergyLevel(10), memory_pressure=EnergyLevel(90))
        state.end_cycle(at=NOW)
        assert state.energy.creative.value > 10
        assert state.energy.memory_pressure.value < 90

    def test_state_round_trips_through_a_checkpoint(self):
        state = CircadianState()
        state.begin_cycle(cycle_id="cycle_test0001", at=NOW)
        state.enter(CircadianPolicy().decide(state, now=NOW))
        state.recent_novelty = 71.5
        restored = CircadianState.from_dict(state.as_dict())
        assert restored.cycle_id == state.cycle_id
        assert restored.phase is state.phase
        assert restored.recent_novelty == 71.5
        assert restored.phases_visited == state.phases_visited
