"""Domain exception hierarchy.

Every failure the creative brain can reason about is modelled here so that the
application layer never has to catch infrastructure-specific errors.
"""

from __future__ import annotations


class CreativeBrainError(Exception):
    """Root of every error raised by the creative brain."""


# --- domain rule violations -------------------------------------------------


class DomainRuleViolation(CreativeBrainError):
    """A domain invariant was violated."""


class InvalidStateTransition(DomainRuleViolation):
    """An artifact was asked to move to a state its lifecycle forbids."""

    def __init__(self, artifact: str, source: str, target: str) -> None:
        super().__init__(f"{artifact}: transition {source} -> {target} is not allowed")
        self.artifact = artifact
        self.source = source
        self.target = target


class InvalidCreativeScore(DomainRuleViolation):
    """A score fell outside the canonical 0..100 range."""


class InvalidCreativeDistance(DomainRuleViolation):
    """A creative distance fell outside the canonical 0..100 range."""


class InvalidEnergyLevel(DomainRuleViolation):
    """An energy gauge fell outside the canonical 0..100 range."""


class ImmutableCoreDnaViolation(DomainRuleViolation):
    """Something tried to mutate the protected CORE_DNA."""


class ConstitutionViolation(DomainRuleViolation):
    """A candidate breached a non-negotiable article of the creative constitution."""


class EmptyTournamentError(DomainRuleViolation):
    """A tournament was run without any competitors."""


# --- execution failures -----------------------------------------------------


class ExecutionFailure(CreativeBrainError):
    """A collaborating component failed while executing work."""


class AgentExecutionFailure(ExecutionFailure):
    """An agent failed to produce a usable, schema-valid answer."""

    def __init__(self, agent: str, reason: str) -> None:
        super().__init__(f"agent '{agent}' failed: {reason}")
        self.agent = agent
        self.reason = reason


class SchemaViolation(AgentExecutionFailure):
    """An agent answered with a payload that does not match its declared schema."""


class MemoryFailure(ExecutionFailure):
    """Memory could not be read, written or consolidated."""


class ResearchFailure(ExecutionFailure):
    """External observation/research could not be completed."""


class ClockDecisionFailure(ExecutionFailure):
    """The circadian policy could not produce a decision."""


class TournamentFailure(ExecutionFailure):
    """A creative tournament could not be completed."""


class PersistenceFailure(ExecutionFailure):
    """A repository could not satisfy a read/write."""


class BudgetExceeded(ExecutionFailure):
    """A configured cost, call or research budget was exhausted."""


class ConfigurationError(CreativeBrainError):
    """The system was started with an invalid or incomplete configuration."""


class AutonomyBoundaryViolation(CreativeBrainError):
    """The creative domain attempted an action outside its autonomy envelope."""
