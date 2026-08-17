"""The multi-agent society.

Builds one real :class:`Agent` per definition, each with its own prompt, its own
model role, its own temperature and its own output schema. There is no single
agent pretending to be many personas — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from creative_brain.agents.base import Agent, AgentContext, AgentHealth
from creative_brain.agents.definitions import DEFAULT_AGENTS, AgentDefinition
from creative_brain.agents.schemas import (
    CharacterSet,
    ConceptDraft,
    ConsequenceReport,
    ConsolidationReport,
    Critique,
    Judgement,
    DreamReport,
    LearningReport,
    LoreReport,
    MetaCognitionReport,
    MutationResult,
    ObsessionReport,
    ObservationBatch,
    ProseArtifact,
    QuestionBatch,
    ResearchReport,
    SeedBatch,
    TitleBatch,
    WorldBible,
)
from pydantic import BaseModel

#: Which schema each agent answers with.
OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "PEDRO_DNA_AGENT": Critique,
    "OBSERVER_AGENT": ObservationBatch,
    "RESEARCH_AGENT": ResearchReport,
    "CURIOSITY_AGENT": QuestionBatch,
    "WHAT_IF_AGENT": SeedBatch,
    "CONCEPT_COLLIDER_AGENT": SeedBatch,
    "INVERSION_AGENT": SeedBatch,
    "PARADOX_AGENT": SeedBatch,
    "CONCEPT_BUILDER": ConceptDraft,
    "PITCH_BUILDER": ProseArtifact,
    "SYNOPSIS_BUILDER": ProseArtifact,
    "EXTREME_CONSEQUENCE_AGENT": ConsequenceReport,
    "REALITY_ANCHOR_AGENT": Critique,
    "BRAZILIAN_REALITY_AGENT": Critique,
    "WORLD_ARCHITECT_AGENT": WorldBible,
    "CHARACTER_ARCHITECT_AGENT": CharacterSet,
    "HUMAN_DRAMA_AGENT": Critique,
    "ELEGANCE_AGENT": Critique,
    "ANTI_CLICHE_AGENT": Critique,
    "NOVELTY_AGENT": Critique,
    "TITLE_AGENT": TitleBatch,
    "MARKET_AGENT": Critique,
    "LORE_CONNECTION_AGENT": LoreReport,
    "RED_TEAM_AGENT": Critique,
    "BLUE_TEAM_AGENT": Critique,
    "CREATIVE_JUDGE_AGENT": Judgement,
    "THE_UNKNOWN_AGENT": SeedBatch,
    "OBSESSION_AGENT": ObsessionReport,
    "MUTATION_AGENT": MutationResult,
    "DREAM_AGENT": DreamReport,
    "MEMORY_AGENT": ConsolidationReport,
    "LEARNING_AGENT": LearningReport,
    "META_COGNITION_AGENT": MetaCognitionReport,
}

#: The critics whose opinions feed the tournament scoreboard.
CRITIC_AGENTS: tuple[str, ...] = (
    "PEDRO_DNA_AGENT",
    "ANTI_CLICHE_AGENT",
    "NOVELTY_AGENT",
    "REALITY_ANCHOR_AGENT",
    "BRAZILIAN_REALITY_AGENT",
    "HUMAN_DRAMA_AGENT",
    "ELEGANCE_AGENT",
    "MARKET_AGENT",
    "RED_TEAM_AGENT",
    "BLUE_TEAM_AGENT",
)

#: The divergent generators fired during CREATION.
GENERATOR_AGENTS: tuple[str, ...] = (
    "WHAT_IF_AGENT",
    "CONCEPT_COLLIDER_AGENT",
    "INVERSION_AGENT",
    "PARADOX_AGENT",
    "THE_UNKNOWN_AGENT",
)


@dataclass
class AgentSociety:
    """The registry of live agents."""

    agents: dict[str, Agent[Any]]
    definitions: dict[str, AgentDefinition]

    @classmethod
    def build(
        cls,
        context: AgentContext,
        *,
        definitions: tuple[AgentDefinition, ...] = DEFAULT_AGENTS,
    ) -> AgentSociety:
        """Instantiate every enabled agent that has a declared output schema."""
        agents: dict[str, Agent[Any]] = {}
        index: dict[str, AgentDefinition] = {}
        for definition in definitions:
            index[definition.id] = definition
            model = OUTPUT_MODELS.get(definition.id)
            if model is None or not definition.enabled:
                # BIOLOGICAL_CLOCK_AGENT has no LLM schema: it runs on a pure
                # domain policy so the rhythm stays deterministic and testable.
                continue
            agents[definition.id] = Agent(
                definition=definition, output_model=model, context=context
            )
        return cls(agents=agents, definitions=index)

    def get(self, agent_id: str) -> Agent[Any]:
        """Fetch a live agent."""
        agent = self.agents.get(agent_id)
        if agent is None:
            raise KeyError(f"agent '{agent_id}' is not registered or is disabled")
        return agent

    def has(self, agent_id: str) -> bool:
        """Whether an agent is live."""
        return agent_id in self.agents

    def critics(self) -> list[Agent[Any]]:
        """Every critic that scores candidates."""
        return [self.agents[a] for a in CRITIC_AGENTS if a in self.agents]

    def generators(self) -> list[Agent[Any]]:
        """Every divergent generator."""
        return [self.agents[a] for a in GENERATOR_AGENTS if a in self.agents]

    def health(self) -> dict[str, AgentHealth]:
        """Health of every live agent."""
        return {agent_id: agent.health for agent_id, agent in self.agents.items()}

    def unhealthy(self) -> list[str]:
        """Agents currently misbehaving."""
        return [aid for aid, agent in self.agents.items() if agent.health.is_unhealthy]

    def catalogue(self) -> list[dict[str, Any]]:
        """Every declared agent with its decision rights, for ``agents list``."""
        return [
            {
                **definition.as_dict(),
                "live": agent_id in self.agents,
                "health": (
                    self.agents[agent_id].health.as_dict() if agent_id in self.agents else None
                ),
            }
            for agent_id, definition in self.definitions.items()
        ]


__all__ = ["CRITIC_AGENTS", "GENERATOR_AGENTS", "OUTPUT_MODELS", "AgentSociety"]
