"""Configuration loading.

Nothing important is hard-coded. Every weight, threshold, budget and feature
flag arrives from ``config/*.yaml`` (overridable by environment variables) and
is turned into a typed domain policy here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from creative_brain.agents.definitions import (
    DEFAULT_AGENTS,
    AgentDefinition,
    DecisionRight,
)
from creative_brain.application.context import CycleTargets, FeatureFlags
from creative_brain.domain.entities.tournament import TournamentFunnel
from creative_brain.domain.exceptions import ConfigurationError
from creative_brain.domain.policies.autonomy import AutonomyPolicy
from creative_brain.domain.policies.circadian import CircadianPolicy
from creative_brain.domain.policies.constitution import ConstitutionPolicy
from creative_brain.domain.policies.dna_evolution import DnaEvolutionPolicy
from creative_brain.domain.policies.exploration import ExplorationPolicy
from creative_brain.domain.policies.memory_policy import MemoryPolicy
from creative_brain.domain.policies.mutation import MutationPolicy
from creative_brain.domain.policies.scoring import ScoringPolicy


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"{path} must contain a YAML mapping")
    return data


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass
class BrainConfig:
    """Everything the composition root needs to build a running brain."""

    root: Path
    scoring: dict[str, Any] = field(default_factory=dict)
    clock: dict[str, Any] = field(default_factory=dict)
    models: dict[str, Any] = field(default_factory=dict)
    autonomy: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    agents: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> BrainConfig:
        """Read every configuration file under ``<root>/config``."""
        config_dir = root / "config"
        return cls(
            root=root,
            scoring=_load_yaml(config_dir / "scoring.yaml"),
            clock=_load_yaml(config_dir / "biological_clock.yaml"),
            models=_load_yaml(config_dir / "models.yaml"),
            autonomy=_load_yaml(config_dir / "autonomy.yaml"),
            memory=_load_yaml(config_dir / "memory.yaml"),
            agents=_load_yaml(config_dir / "agents.yaml"),
        )

    # ------------------------------------------------------------- policies

    def scoring_policy(self) -> ScoringPolicy:
        """Weights and the guards that stop a number from winning on its own."""
        guards = self.scoring.get("guards") or {}
        return ScoringPolicy.from_mapping(
            self.scoring.get("weights") or {},
            max_commercial_share=float(guards.get("max_commercial_share", 0.25)),
            min_originality=float(guards.get("min_originality", 35.0)),
            blocked_score_ceiling=float(guards.get("blocked_score_ceiling", 45.0)),
        )

    def exploration_policy(self) -> ExplorationPolicy:
        """How effort is split across comfort, edge and unknown territory."""
        return ExplorationPolicy.from_mapping(
            self.scoring.get("exploration") or {},
            unknown_enabled=self.feature_flags().unknown_zone_enabled,
        )

    def circadian_policy(self) -> CircadianPolicy:
        """The thresholds that shape the rhythm."""
        thresholds = self.clock.get("thresholds") or {}
        gates = self.clock.get("gates") or {}
        budgets = self.clock.get("budgets") or {}
        toggles = self.clock.get("toggles") or {}
        phases = self.clock.get("phases") or {}
        flags = self.feature_flags()
        return CircadianPolicy(
            creative_floor=float(thresholds.get("creative_floor", 25.0)),
            research_floor=float(thresholds.get("research_floor", 20.0)),
            critical_floor=float(thresholds.get("critical_floor", 20.0)),
            memory_pressure_ceiling=float(thresholds.get("memory_pressure_ceiling", 70.0)),
            novelty_pressure_ceiling=float(thresholds.get("novelty_pressure_ceiling", 65.0)),
            novelty_floor=float(thresholds.get("novelty_floor", 40.0)),
            duplicate_rate_ceiling=float(thresholds.get("duplicate_rate_ceiling", 0.35)),
            failure_rate_ceiling=float(thresholds.get("failure_rate_ceiling", 0.30)),
            min_observations_before_creating=int(
                gates.get("min_observations_before_creating", 3)
            ),
            min_seeds_before_tournament=int(gates.get("min_seeds_before_tournament", 4)),
            max_llm_calls_per_cycle=_env_int(
                "CREATIVE_BRAIN_MAX_LLM_CALLS_PER_CYCLE",
                int(budgets.get("max_llm_calls_per_cycle", 400)),
            ),
            max_cost_usd_per_cycle=_env_float(
                "CREATIVE_BRAIN_MAX_USD_PER_CYCLE",
                float(budgets.get("max_cost_usd_per_cycle", 5.0)),
            ),
            dream_mode_enabled=bool(toggles.get("dream_mode_enabled", True))
            and flags.dream_mode_enabled,
            exploration_enabled=bool(toggles.get("exploration_enabled", True)),
            second_wind_enabled=bool(toggles.get("second_wind_enabled", True)),
            phase_duration_seconds=float(phases.get("duration_seconds", 0.0)),
        )

    def mutation_policy(self) -> MutationPolicy:
        """When a dead idea deserves another life."""
        graveyard = self.memory.get("graveyard") or {}
        return MutationPolicy(
            enabled=self.feature_flags().mutation_enabled,
            min_mutation_potential=float(graveyard.get("min_mutation_potential", 40.0)),
        )

    def memory_policy(self) -> MemoryPolicy:
        """Decay, retrieval and what may become a principle."""
        policy = self.memory.get("policy") or {}
        return MemoryPolicy(
            episodic_decay_per_cycle=float(policy.get("episodic_decay_per_cycle", 0.92)),
            retrieval_floor=float(policy.get("retrieval_floor", 8.0)),
            max_retrieved=int(policy.get("max_retrieved", 12)),
            min_events_per_principle=int(policy.get("min_events_per_principle", 2)),
            idea_half_life_cycles=int(policy.get("idea_half_life_cycles", 12)),
        )

    def dna_policy(self) -> DnaEvolutionPolicy:
        """Bounds on autonomous learning."""
        self_eval = self.autonomy.get("self_evaluation") or {}
        return DnaEvolutionPolicy(
            enabled=bool(self_eval.get("may_update_evolving_dna", True)),
            max_new_entries_per_cycle=int(self_eval.get("max_new_dna_entries_per_cycle", 6)),
            max_weight_drift=float(self_eval.get("max_weight_drift", 0.05)),
        )

    def constitution_policy(self) -> ConstitutionPolicy:
        """The blocking articles, expressed as thresholds."""
        constitution = self.scoring.get("constitution") or {}
        return ConstitutionPolicy(
            min_depth_for_consequence=float(constitution.get("min_depth_for_consequence", 30.0)),
            min_emotional_impact=float(constitution.get("min_emotional_impact", 30.0)),
        )

    def autonomy_policy(self) -> AutonomyPolicy:
        """The envelope. Restricted actions are never configurable into autonomy."""
        limits = self.autonomy.get("limits") or {}
        return AutonomyPolicy(
            max_cost_usd_per_cycle=float(limits.get("max_cost_usd_per_cycle", 5.0))
        )

    # ---------------------------------------------------------------- other

    def feature_flags(self) -> FeatureFlags:
        """Runtime switches."""
        flags = self.autonomy.get("feature_flags") or {}
        return FeatureFlags(
            dream_mode_enabled=bool(flags.get("dream_mode_enabled", True)),
            external_research_enabled=bool(flags.get("external_research_enabled", False)),
            mutation_enabled=bool(flags.get("mutation_enabled", True)),
            unknown_zone_enabled=bool(flags.get("unknown_zone_enabled", True)),
            production_handoff_enabled=bool(flags.get("production_handoff_enabled", False)),
            lore_connections_enabled=bool(flags.get("lore_connections_enabled", True)),
            meta_cognition_enabled=bool(flags.get("meta_cognition_enabled", True)),
        )

    def cycle_targets(self) -> CycleTargets:
        """How much the engine tries to produce per cycle."""
        targets = self.agents.get("cycle_targets") or {}
        return CycleTargets(
            observations=int(targets.get("observations", 8)),
            questions_per_observation=int(targets.get("questions_per_observation", 2)),
            seeds_per_generator=int(targets.get("seeds_per_generator", 4)),
            concepts=int(targets.get("concepts", 12)),
            research_topics=int(targets.get("research_topics", 2)),
            dream_fragments=int(targets.get("dream_fragments", 5)),
            mutations=int(targets.get("mutations", 3)),
            titles=int(targets.get("titles", 3)),
        )

    def tournament_funnel(self, *, pool_size: int | None = None) -> TournamentFunnel:
        """The elimination ladder, scaled down when the pool is smaller than the funnel."""
        raw = (self.scoring.get("tournament") or {}).get("funnel") or []
        pairs = [(str(step["stage"]), int(step["survivors"])) for step in raw]
        if not pairs:
            pairs = [
                ("CONCEPT", 30),
                ("PREMISE", 10),
                ("PITCH", 5),
                ("CANDIDATE", 4),
                ("FINALIST", 3),
            ]
        if pool_size is not None:
            pairs = _scale_funnel(pairs, pool_size)
        return TournamentFunnel.from_pairs(pairs)

    def max_similarity_between_survivors(self) -> float:
        """Redundancy ceiling inside a single tournament round."""
        return float(
            (self.scoring.get("tournament") or {}).get("max_similarity_between_survivors", 0.60)
        )

    def duplicate_threshold(self) -> float:
        """Similarity at or above which two ideas count as duplicates."""
        return float((self.scoring.get("novelty") or {}).get("duplicate_threshold", 0.62))

    def distance_measurement_weight(self) -> float:
        """How far measurement may pull the intended creative distance."""
        return float(
            (self.scoring.get("creative_distance") or {}).get("measurement_weight", 0.35)
        )

    def agent_definitions(self) -> tuple[AgentDefinition, ...]:
        """Default definitions with ``config/agents.yaml`` overrides applied."""
        overrides = self.agents.get("agents") or {}
        definitions: list[AgentDefinition] = []
        for definition in DEFAULT_AGENTS:
            override = overrides.get(definition.id)
            definitions.append(
                _apply_override(definition, override) if isinstance(override, dict) else definition
            )
        return tuple(definitions)

    def provider(self) -> str:
        """Which LLM provider to use."""
        return os.environ.get(
            "CREATIVE_BRAIN_LLM_PROVIDER", str(self.models.get("provider", "mock"))
        ).strip().lower()

    def routing(self) -> dict[str, dict[str, str]]:
        """Role -> {provider, model} routing table."""
        raw = self.models.get("routing") or {}
        return {
            str(role): {
                "provider": str((cfg or {}).get("provider", self.provider())),
                "model": str((cfg or {}).get("model", "")),
            }
            for role, cfg in raw.items()
        }

    def model_limits(self) -> dict[str, Any]:
        """Token, rate, retry and circuit-breaker limits."""
        return dict(self.models.get("limits") or {})

    def random_seed(self) -> int:
        """The deterministic seed recorded in every cycle manifest."""
        return _env_int("CREATIVE_BRAIN_RANDOM_SEED", 20260807)

    def vector_backend(self) -> str:
        """Which vector memory backend to build."""
        return str((self.memory.get("vector_memory") or {}).get("backend", "lexical"))


def _apply_override(definition: AgentDefinition, override: dict[str, Any]) -> AgentDefinition:
    """Apply a YAML override onto a default agent definition."""
    from dataclasses import replace

    changes: dict[str, Any] = {}
    if "enabled" in override:
        changes["enabled"] = bool(override["enabled"])
    if "temperature" in override:
        changes["temperature"] = float(override["temperature"])
    if "prompt" in override:
        changes["prompt"] = str(override["prompt"])
    if "objective" in override:
        changes["objective"] = str(override["objective"])
    if "decision_rights" in override:
        changes["decision_rights"] = tuple(
            DecisionRight(str(r)) for r in override["decision_rights"]
        )
    return replace(definition, **changes) if changes else definition


def _scale_funnel(pairs: list[tuple[str, int]], pool_size: int) -> list[tuple[str, int]]:
    """Shrink the funnel so it still eliminates when the pool is small.

    A funnel wider than the pool would promote everyone, and the tournament
    would stop being a tournament. Every round except the last is forced to
    eliminate at least one candidate; the last round keeps its configured width
    so the judge still receives several finalists to choose between.
    """
    scaled: list[tuple[str, int]] = []
    previous = max(1, pool_size)
    for index, (stage, survivors) in enumerate(pairs):
        is_last = index == len(pairs) - 1
        width = min(survivors, previous)
        if width >= previous and not is_last:
            width = max(1, previous - 1)
        previous = width
        scaled.append((stage, width))
    return scaled


__all__ = ["BrainConfig"]
