"""The creative lifecycle state machine.

No artifact changes stage without an explicit, named rule. This module is the
single source of truth for those rules; the entity only enforces them.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from creative_brain.domain.exceptions import InvalidStateTransition


class CreativeStage(StrEnum):
    """Every stage a creative artifact can occupy."""

    # --- the main line ---
    SEED = "SEED"
    CONCEPT = "CONCEPT"
    PREMISE = "PREMISE"
    PITCH = "PITCH"
    EXPERIMENT = "EXPERIMENT"
    CANDIDATE = "CANDIDATE"
    FINALIST = "FINALIST"
    APPROVED = "APPROVED"
    PROJECT = "PROJECT"
    PRODUCTION_READY = "PRODUCTION_READY"

    # --- alternative destinies ---
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"
    GRAVEYARD = "GRAVEYARD"
    MUTATION_POOL = "MUTATION_POOL"
    SLEEPING = "SLEEPING"


ADVANCING_ORDER: tuple[CreativeStage, ...] = (
    CreativeStage.SEED,
    CreativeStage.CONCEPT,
    CreativeStage.PREMISE,
    CreativeStage.PITCH,
    CreativeStage.EXPERIMENT,
    CreativeStage.CANDIDATE,
    CreativeStage.FINALIST,
    CreativeStage.APPROVED,
    CreativeStage.PROJECT,
    CreativeStage.PRODUCTION_READY,
)

TERMINAL_STAGES: frozenset[CreativeStage] = frozenset(
    {CreativeStage.PRODUCTION_READY, CreativeStage.GRAVEYARD}
)

#: Stages from which an idea can still be revived by Dream Mode / mutation.
REVIVABLE_STAGES: frozenset[CreativeStage] = frozenset(
    {
        CreativeStage.REJECTED,
        CreativeStage.ARCHIVED,
        CreativeStage.GRAVEYARD,
        CreativeStage.MUTATION_POOL,
        CreativeStage.SLEEPING,
    }
)

_FALLIBLE = (
    CreativeStage.REJECTED,
    CreativeStage.ARCHIVED,
    CreativeStage.SLEEPING,
)

_TRANSITIONS: Mapping[CreativeStage, frozenset[CreativeStage]] = MappingProxyType(
    {
        CreativeStage.SEED: frozenset({CreativeStage.CONCEPT, *_FALLIBLE}),
        CreativeStage.CONCEPT: frozenset({CreativeStage.PREMISE, *_FALLIBLE}),
        CreativeStage.PREMISE: frozenset({CreativeStage.PITCH, *_FALLIBLE}),
        CreativeStage.PITCH: frozenset(
            {CreativeStage.EXPERIMENT, CreativeStage.CANDIDATE, *_FALLIBLE}
        ),
        CreativeStage.EXPERIMENT: frozenset({CreativeStage.CANDIDATE, *_FALLIBLE}),
        CreativeStage.CANDIDATE: frozenset({CreativeStage.FINALIST, *_FALLIBLE}),
        CreativeStage.FINALIST: frozenset({CreativeStage.APPROVED, *_FALLIBLE}),
        CreativeStage.APPROVED: frozenset({CreativeStage.PROJECT, CreativeStage.ARCHIVED}),
        CreativeStage.PROJECT: frozenset({CreativeStage.PRODUCTION_READY, CreativeStage.ARCHIVED}),
        CreativeStage.PRODUCTION_READY: frozenset(),
        # --- alternative destinies ---
        CreativeStage.REJECTED: frozenset(
            {CreativeStage.MUTATION_POOL, CreativeStage.GRAVEYARD, CreativeStage.ARCHIVED}
        ),
        CreativeStage.ARCHIVED: frozenset({CreativeStage.MUTATION_POOL, CreativeStage.GRAVEYARD}),
        # A grave is never emptied: resurrection *copies* the idea into a fresh
        # mutation-pool lineage rather than erasing the record.
        CreativeStage.GRAVEYARD: frozenset({CreativeStage.MUTATION_POOL}),
        CreativeStage.MUTATION_POOL: frozenset(
            {CreativeStage.SEED, CreativeStage.CONCEPT, CreativeStage.GRAVEYARD}
        ),
        CreativeStage.SLEEPING: frozenset(
            {CreativeStage.CONCEPT, CreativeStage.MUTATION_POOL, CreativeStage.ARCHIVED}
        ),
    }
)


def allowed_targets(stage: CreativeStage) -> frozenset[CreativeStage]:
    """Stages reachable from ``stage``."""
    return _TRANSITIONS[stage]


def can_transition(source: CreativeStage, target: CreativeStage) -> bool:
    """Whether the lifecycle permits ``source -> target``."""
    return target in _TRANSITIONS[source]


def assert_transition(artifact: str, source: CreativeStage, target: CreativeStage) -> None:
    """Raise :class:`InvalidStateTransition` when the move is not allowed."""
    if not can_transition(source, target):
        raise InvalidStateTransition(artifact, str(source), str(target))


def is_terminal(stage: CreativeStage) -> bool:
    """Whether nothing further can happen to an artifact in this stage."""
    return stage in TERMINAL_STAGES


def is_alive(stage: CreativeStage) -> bool:
    """Whether the artifact is still competing on the main line."""
    return stage in ADVANCING_ORDER


def next_stage(stage: CreativeStage) -> CreativeStage:
    """The next stage on the main line."""
    if stage not in ADVANCING_ORDER:
        raise InvalidStateTransition("lifecycle", str(stage), "<next>")
    index = ADVANCING_ORDER.index(stage)
    if index + 1 >= len(ADVANCING_ORDER):
        raise InvalidStateTransition("lifecycle", str(stage), "<next>")
    return ADVANCING_ORDER[index + 1]
