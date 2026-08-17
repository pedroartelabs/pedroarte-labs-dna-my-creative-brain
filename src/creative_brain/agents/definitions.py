"""Agent definitions.

Every agent declares the same contract: role, objective, inputs, outputs,
allowed tools, memory scope, decision rights, prompt and metrics. That contract
is what stops the society from degenerating into "one model wearing costumes".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from creative_brain.ports.outbound.llm import ModelRole


class DecisionRight(StrEnum):
    """What an agent is actually allowed to decide."""

    OBSERVE_ONLY = "observe_only"
    PROPOSE = "propose"
    SCORE = "score"
    VETO = "veto"
    DECIDE = "decide"
    LEARN = "learn"
    SCHEDULE = "schedule"


class MemoryScope(StrEnum):
    """How much of the memory an agent may read."""

    NONE = "none"
    CYCLE = "cycle"
    CREATIVE = "creative"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """The declaration of one agent in the society."""

    id: str
    role: str
    objective: str
    prompt: str
    task: str
    model_role: ModelRole = ModelRole.CREATIVE
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    memory_scope: MemoryScope = MemoryScope.CYCLE
    decision_rights: tuple[DecisionRight, ...] = (DecisionRight.PROPOSE,)
    metrics: tuple[str, ...] = ()
    temperature: float = 0.8
    enabled: bool = True

    def may(self, right: DecisionRight) -> bool:
        """Whether the agent holds a decision right."""
        return right in self.decision_rights

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view, used by ``creative-brain agents list``."""
        return {
            "id": self.id,
            "role": self.role,
            "objective": self.objective,
            "prompt": self.prompt,
            "task": self.task,
            "model_role": str(self.model_role),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "allowed_tools": list(self.allowed_tools),
            "memory_scope": str(self.memory_scope),
            "decision_rights": [str(r) for r in self.decision_rights],
            "metrics": list(self.metrics),
            "temperature": self.temperature,
            "enabled": self.enabled,
        }


def _d(
    agent_id: str,
    role: str,
    objective: str,
    prompt: str,
    task: str,
    *,
    model_role: ModelRole = ModelRole.CREATIVE,
    rights: tuple[DecisionRight, ...] = (DecisionRight.PROPOSE,),
    scope: MemoryScope = MemoryScope.CYCLE,
    temperature: float = 0.8,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    metrics: tuple[str, ...] = (),
) -> AgentDefinition:
    return AgentDefinition(
        id=agent_id,
        role=role,
        objective=objective,
        prompt=prompt,
        task=task,
        model_role=model_role,
        inputs=inputs,
        outputs=outputs,
        memory_scope=scope,
        decision_rights=rights,
        temperature=temperature,
        metrics=metrics,
    )


#: The default society. ``config/agents.yaml`` overrides any field of any agent.
DEFAULT_AGENTS: tuple[AgentDefinition, ...] = (
    _d(
        "PEDRO_DNA_AGENT",
        "guardian of the creative mechanism",
        "Decide whether a candidate reproduces the creative mechanism or merely imitates its surface.",
        "pedro_dna_agent",
        "pedro_dna.evaluate",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE, DecisionRight.VETO),
        scope=MemoryScope.FULL,
        temperature=0.3,
        inputs=("concept", "core_dna"),
        outputs=("critique",),
        metrics=("identity_score", "veto_rate"),
    ),
    _d(
        "OBSERVER_AGENT",
        "sensor of the world",
        "Capture facts, trends, oddities and contradictions. Never write a story.",
        "observer_agent",
        "observer.capture",
        model_role=ModelRole.RESEARCH,
        rights=(DecisionRight.OBSERVE_ONLY,),
        scope=MemoryScope.NONE,
        temperature=0.7,
        outputs=("observations",),
        metrics=("observations_captured",),
    ),
    _d(
        "RESEARCH_AGENT",
        "deep investigator",
        "Investigate topics the engine found interesting, through research ports only.",
        "research_agent",
        "research.investigate",
        model_role=ModelRole.RESEARCH,
        scope=MemoryScope.CYCLE,
        temperature=0.4,
        inputs=("topic",),
        outputs=("finding",),
        metrics=("research_calls",),
    ),
    _d(
        "CURIOSITY_AGENT",
        "question maker",
        "Turn observations into questions worth a whole book.",
        "curiosity_agent",
        "curiosity.questions",
        temperature=0.9,
        inputs=("observation",),
        outputs=("questions",),
        metrics=("questions_generated",),
    ),
    _d(
        "WHAT_IF_AGENT",
        "hypothesis generator",
        "Turn facts and questions into progressively deeper 'what if' hypotheses.",
        "what_if_agent",
        "what_if.hypotheses",
        temperature=0.95,
        inputs=("question",),
        outputs=("seeds",),
    ),
    _d(
        "CONCEPT_COLLIDER_AGENT",
        "collider of unrelated concepts",
        "Smash apparently disconnected concepts together until a third thing appears.",
        "concept_collider_agent",
        "collider.collide",
        temperature=1.0,
        outputs=("seeds",),
    ),
    _d(
        "INVERSION_AGENT",
        "inverter",
        "Invert the axis of a concept: life/death, wealth/debt, identity/property.",
        "inversion_agent",
        "inversion.invert",
        temperature=0.9,
        outputs=("seeds",),
    ),
    _d(
        "PARADOX_AGENT",
        "paradox hunter",
        "Find conceptual paradoxes strong enough to carry a whole world.",
        "paradox_agent",
        "paradox.find",
        temperature=0.9,
        outputs=("seeds",),
    ),
    _d(
        "CONCEPT_BUILDER",
        "concept builder",
        "Turn a raw seed into a structured concept with a mechanism, not an atmosphere.",
        "concept_builder",
        "concept.draft",
        temperature=0.85,
        inputs=("seed", "question", "dna", "zone"),
        outputs=("concept",),
        metrics=("concepts_built",),
    ),
    _d(
        "PITCH_BUILDER",
        "pitch writer",
        "Write the commercial positioning of an approved project.",
        "pitch_builder",
        "pitch.build",
        temperature=0.7,
        inputs=("subject",),
        outputs=("text",),
    ),
    _d(
        "SYNOPSIS_BUILDER",
        "synopsis writer",
        "Write the three-act synopsis of an approved project.",
        "synopsis_builder",
        "synopsis.build",
        model_role=ModelRole.STRUCTURING,
        temperature=0.7,
        inputs=("subject",),
        outputs=("text",),
    ),
    _d(
        "EXTREME_CONSEQUENCE_AGENT",
        "consequence simulator",
        "Follow a premise to T+1, T+10, T+50 and T+100 years and report what breaks.",
        "extreme_consequence_agent",
        "consequence.simulate",
        model_role=ModelRole.STRUCTURING,
        temperature=0.6,
        inputs=("premise",),
        outputs=("horizons",),
    ),
    _d(
        "REALITY_ANCHOR_AGENT",
        "plausibility anchor",
        "Ask how this dystopia could emerge organically from present reality.",
        "reality_anchor_agent",
        "reality_anchor.check",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE,),
        temperature=0.4,
        outputs=("critique",),
    ),
    _d(
        "BRAZILIAN_REALITY_AGENT",
        "specialist in Brazilian reality",
        "Prevent an American story merely translated into Portuguese.",
        "brazilian_reality_agent",
        "brazilian_reality.localize",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE, DecisionRight.VETO),
        temperature=0.5,
        outputs=("critique",),
    ),
    _d(
        "WORLD_ARCHITECT_AGENT",
        "world builder",
        "Build rules, economy, institutions, classes, language, taboos and power.",
        "world_architect_agent",
        "world_architect.build",
        model_role=ModelRole.STRUCTURING,
        temperature=0.7,
        outputs=("world_bible",),
    ),
    _d(
        "CHARACTER_ARCHITECT_AGENT",
        "character builder",
        "Build characters that occupy different positions towards the system.",
        "character_architect_agent",
        "character_architect.build",
        model_role=ModelRole.STRUCTURING,
        temperature=0.75,
        outputs=("characters",),
    ),
    _d(
        "HUMAN_DRAMA_AGENT",
        "keeper of human stakes",
        "Answer why a human being would care. Convert high concept into love, fear, debt, family.",
        "human_drama_agent",
        "human_drama.ground",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE, DecisionRight.VETO),
        temperature=0.6,
        outputs=("critique",),
    ),
    _d(
        "ELEGANCE_AGENT",
        "aesthetic critic",
        "Evaluate sophistication, subtext, tension and atmosphere; reject gratuitous shock.",
        "elegance_agent",
        "elegance.evaluate",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE,),
        temperature=0.5,
        outputs=("critique",),
    ),
    _d(
        "ANTI_CLICHE_AGENT",
        "prosecutor of derivativeness",
        "Try to prove the idea is derivative. If 'what is new' is weak, reject.",
        "anti_cliche_agent",
        "anti_cliche.attack",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE, DecisionRight.VETO),
        temperature=0.4,
        outputs=("critique",),
        metrics=("rejections_issued",),
    ),
    _d(
        "NOVELTY_AGENT",
        "novelty assessor",
        "Compare against prior work, prior ideas, current candidates and the graveyard.",
        "novelty_agent",
        "novelty.evaluate",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE,),
        scope=MemoryScope.FULL,
        temperature=0.3,
        outputs=("critique",),
        metrics=("average_novelty_score",),
    ),
    _d(
        "TITLE_AGENT",
        "title maker",
        "Propose short, conceptual titles with a second meaning tied to the premise.",
        "title_agent",
        "title.propose",
        temperature=0.9,
        outputs=("titles",),
    ),
    _d(
        "MARKET_AGENT",
        "market reader",
        "Assess pitch, audience, cover, trailer and adaptability. Never decides artistic quality.",
        "market_agent",
        "market.evaluate",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE,),
        temperature=0.5,
        outputs=("critique",),
    ),
    _d(
        "LORE_CONNECTION_AGENT",
        "connector of works",
        "Suggest possible links between works. Never force a shared universe.",
        "lore_connection_agent",
        "lore.connect",
        scope=MemoryScope.FULL,
        temperature=0.7,
        outputs=("connections",),
    ),
    _d(
        "RED_TEAM_AGENT",
        "destroyer",
        "Destroy the idea: where does it break, bore, or become predictable?",
        "red_team_agent",
        "red_team.attack",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE, DecisionRight.VETO),
        temperature=0.6,
        outputs=("critique",),
        metrics=("agent_disagreement_rate",),
    ),
    _d(
        "BLUE_TEAM_AGENT",
        "defender",
        "Defend the same idea against the red team, with arguments not adjectives.",
        "blue_team_agent",
        "blue_team.defend",
        model_role=ModelRole.CRITICISM,
        rights=(DecisionRight.SCORE,),
        temperature=0.6,
        outputs=("critique",),
    ),
    _d(
        "CREATIVE_JUDGE_AGENT",
        "judge",
        "Judge using evidence from other agents. Never create, never rewrite, never protect.",
        "creative_judge_agent",
        "judge.verdict",
        model_role=ModelRole.JUDGING,
        rights=(DecisionRight.DECIDE, DecisionRight.VETO),
        scope=MemoryScope.FULL,
        temperature=0.2,
        outputs=("judgement",),
        metrics=("ideas_approved_total", "ideas_rejected_total"),
    ),
    _d(
        "THE_UNKNOWN_AGENT",
        "explorer of the unthought",
        "Ask what Pedro Arte has not thought of yet. Work in the UNKNOWN_ZONE.",
        "the_unknown_agent",
        "unknown.propose",
        model_role=ModelRole.DREAMING,
        temperature=1.0,
        outputs=("seeds",),
        metrics=("unknown_zone_share",),
    ),
    _d(
        "OBSESSION_AGENT",
        "reader of recurrences",
        "Tell a real obsession apart from disguised repetition.",
        "obsession_agent",
        "obsession.analyze",
        model_role=ModelRole.CRITICISM,
        scope=MemoryScope.FULL,
        temperature=0.4,
        outputs=("obsessions",),
    ),
    _d(
        "MUTATION_AGENT",
        "mutation engine",
        "Give rejected ideas a structurally different second life.",
        "mutation_agent",
        "mutation.mutate",
        temperature=0.9,
        outputs=("mutation",),
        metrics=("mutation_success_rate",),
    ),
    _d(
        "DREAM_AGENT",
        "subconscious",
        "Freely associate with no plausibility, market, genre or coherence constraint.",
        "dream_agent",
        "dream.associate",
        model_role=ModelRole.DREAMING,
        temperature=1.0,
        outputs=("fragments",),
    ),
    _d(
        "MEMORY_AGENT",
        "consolidator",
        "Consolidate memory. Never confuse a raw event with a learned principle.",
        "memory_agent",
        "memory.consolidate",
        model_role=ModelRole.STRUCTURING,
        rights=(DecisionRight.LEARN,),
        scope=MemoryScope.FULL,
        temperature=0.3,
        outputs=("principles",),
    ),
    _d(
        "LEARNING_AGENT",
        "student of its own cycles",
        "Analyse what won, what lost, what is saturated. May update EVOLVING_DNA only.",
        "learning_agent",
        "learning.reflect",
        model_role=ModelRole.JUDGING,
        rights=(DecisionRight.LEARN,),
        scope=MemoryScope.FULL,
        temperature=0.35,
        outputs=("learning",),
    ),
    _d(
        "META_COGNITION_AGENT",
        "observer of the society",
        "Ask whether the agents are thinking differently or repeating one another.",
        "meta_cognition_agent",
        "meta_cognition.analyze",
        model_role=ModelRole.JUDGING,
        scope=MemoryScope.FULL,
        temperature=0.4,
        outputs=("meta",),
        metrics=("diversity_score",),
    ),
    _d(
        "BIOLOGICAL_CLOCK_AGENT",
        "circadian governor",
        "Own WHEN: decide the next phase from energy, backlogs, quality and budget.",
        "biological_clock_agent",
        "clock.decide",
        model_role=ModelRole.JUDGING,
        rights=(DecisionRight.SCHEDULE, DecisionRight.DECIDE),
        scope=MemoryScope.FULL,
        temperature=0.0,
        outputs=("circadian_decision",),
        metrics=("circadian_phase_duration",),
    ),
)

AGENT_INDEX: dict[str, AgentDefinition] = {a.id: a for a in DEFAULT_AGENTS}


def default_definition(agent_id: str) -> AgentDefinition:
    """Look up a default definition by id."""
    return AGENT_INDEX[agent_id]


__all__ = [
    "AGENT_INDEX",
    "DEFAULT_AGENTS",
    "AgentDefinition",
    "DecisionRight",
    "MemoryScope",
    "default_definition",
]
