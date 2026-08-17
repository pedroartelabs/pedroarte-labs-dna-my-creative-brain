"""The autonomy envelope: AUTONOMOUS CREATIVITY + CONTROLLED INFRASTRUCTURE.

The creative loop needs no human approval. Infrastructure, money, credentials
and anything that leaves this machine do. This policy is the single place that
distinction is encoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.domain.exceptions import AutonomyBoundaryViolation


class CreativeAction(StrEnum):
    """Actions the engine performs on its own authority."""

    OBSERVE = "observe"
    RESEARCH = "research"
    FORMULATE_QUESTION = "formulate_question"
    GENERATE_SEED = "generate_seed"
    BUILD_CONCEPT = "build_concept"
    COMBINE_CONCEPTS = "combine_concepts"
    CRITIQUE = "critique"
    REJECT_IDEA = "reject_idea"
    MUTATE_IDEA = "mutate_idea"
    RESURRECT_IDEA = "resurrect_idea"
    RUN_TOURNAMENT = "run_tournament"
    JUDGE = "judge"
    APPROVE_PROJECT = "approve_project"
    ARCHIVE_PROJECT = "archive_project"
    WRITE_OUTPUT = "write_output"
    CONSOLIDATE_MEMORY = "consolidate_memory"
    UPDATE_EVOLVING_DNA = "update_evolving_dna"
    DREAM = "dream"
    DECIDE_SCHEDULE = "decide_schedule"
    START_CYCLE = "start_cycle"


class RestrictedAction(StrEnum):
    """Actions that always require a human, no matter what the engine concludes."""

    DELETE_REPOSITORY = "delete_repository"
    CHANGE_REPOSITORY_VISIBILITY = "change_repository_visibility"
    PUSH_TO_REMOTE = "push_to_remote"
    PUBLISH_EXTERNALLY = "publish_externally"
    SEND_MESSAGE = "send_message"
    MANAGE_CREDENTIALS = "manage_credentials"
    CHANGE_SECURITY_POLICY = "change_security_policy"
    MODIFY_SOURCE_CODE = "modify_source_code"
    MODIFY_CORE_DNA = "modify_core_dna"
    MODIFY_CONSTITUTION = "modify_constitution"
    SPEND_MONEY = "spend_money"
    DELETE_MEMORY = "delete_memory"
    INSTALL_DEPENDENCIES = "install_dependencies"


@dataclass(frozen=True, slots=True)
class AutonomyPolicy:
    """Grants creative authority, denies infrastructural authority."""

    autonomous: frozenset[CreativeAction] = field(
        default_factory=lambda: frozenset(CreativeAction)
    )
    restricted: frozenset[RestrictedAction] = field(
        default_factory=lambda: frozenset(RestrictedAction)
    )
    #: Even the creative loop respects a hard ceiling on external spend.
    max_cost_usd_per_cycle: float = 5.0

    def may(self, action: CreativeAction) -> bool:
        """Whether the engine may perform a creative action unattended."""
        return action in self.autonomous

    def assert_allowed(self, action: CreativeAction) -> None:
        """Raise when a creative action has been disabled by configuration."""
        if not self.may(action):
            raise AutonomyBoundaryViolation(f"creative action '{action}' is disabled")

    def assert_not_restricted(self, action: str) -> None:
        """Raise when the engine attempts anything on the restricted list."""
        normalised = action.strip().lower()
        if normalised in {str(a) for a in self.restricted}:
            raise AutonomyBoundaryViolation(
                f"'{action}' requires a human operator: the creative domain has autonomy "
                "over ideas, never over infrastructure, credentials, publication or spend"
            )

    def requires_human(self, action: str) -> bool:
        """Whether an action sits outside the envelope."""
        return action.strip().lower() in {str(a) for a in self.restricted}

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view, used by ``creative-brain status``."""
        return {
            "autonomous_actions": sorted(str(a) for a in self.autonomous),
            "restricted_actions": sorted(str(a) for a in self.restricted),
            "max_cost_usd_per_cycle": self.max_cost_usd_per_cycle,
        }
