"""The multi-agent society.

Each agent is a real, separately-configured participant with its own prompt,
model role, temperature, output schema and decision rights. Agents never invoke
each other directly — coordination happens through use cases, domain events and
the orchestrator.
"""

from creative_brain.agents.base import Agent, AgentContext, AgentHealth
from creative_brain.agents.definitions import (
    AGENT_INDEX,
    DEFAULT_AGENTS,
    AgentDefinition,
    DecisionRight,
    MemoryScope,
)
from creative_brain.agents.society import (
    CRITIC_AGENTS,
    GENERATOR_AGENTS,
    OUTPUT_MODELS,
    AgentSociety,
)

__all__ = [
    "AGENT_INDEX",
    "CRITIC_AGENTS",
    "DEFAULT_AGENTS",
    "GENERATOR_AGENTS",
    "OUTPUT_MODELS",
    "Agent",
    "AgentContext",
    "AgentDefinition",
    "AgentHealth",
    "AgentSociety",
    "DecisionRight",
    "MemoryScope",
]
