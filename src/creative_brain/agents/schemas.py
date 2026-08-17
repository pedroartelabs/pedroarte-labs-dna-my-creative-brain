"""Structured output schemas for every agent.

Agents answer with validated objects, never with free text that someone has to
parse later. A schema violation is a first-class failure (``SchemaViolation``),
which is what lets the health monitor notice a broken agent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """Base model: unknown keys are dropped, not fatal — models drift."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --- observation ------------------------------------------------------------


class ObservationItem(_Strict):
    """One captured signal."""

    statement: str
    domain: str = "society"
    kind: str = "fact"
    tension: str = ""
    tags: list[str] = Field(default_factory=list)
    salience: float = 50.0


class ObservationBatch(_Strict):
    """What OBSERVER_AGENT returns."""

    observations: list[ObservationItem] = Field(default_factory=list)


class ResearchReport(_Strict):
    """What RESEARCH_AGENT returns."""

    summary: str
    key_facts: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    confidence: float = 50.0


class QuestionItem(_Strict):
    """One creative question."""

    text: str
    provocation: str = ""
    tags: list[str] = Field(default_factory=list)


class QuestionBatch(_Strict):
    """What CURIOSITY_AGENT returns."""

    questions: list[QuestionItem] = Field(default_factory=list)


# --- generation -------------------------------------------------------------


class SeedItem(_Strict):
    """One raw creative seed, whatever mechanism produced it."""

    statement: str
    themes: list[str] = Field(default_factory=list)
    heat: float = 50.0
    axis: str = ""
    paradox: str = ""
    ingredients: list[str] = Field(default_factory=list)
    why_unthought: str = ""


class SeedBatch(_Strict):
    """A batch of seeds; accepts every generator's key so one model fits all."""

    hypotheses: list[SeedItem] = Field(default_factory=list)
    collisions: list[SeedItem] = Field(default_factory=list)
    inversions: list[SeedItem] = Field(default_factory=list)
    paradoxes: list[SeedItem] = Field(default_factory=list)
    proposals: list[SeedItem] = Field(default_factory=list)
    seeds: list[SeedItem] = Field(default_factory=list)

    def all_items(self) -> list[SeedItem]:
        """Every seed regardless of which generator key it arrived under."""
        return [
            *self.hypotheses,
            *self.collisions,
            *self.inversions,
            *self.paradoxes,
            *self.proposals,
            *self.seeds,
        ]


class ConceptDraft(_Strict):
    """What the concept builder returns."""

    title: str
    logline: str
    central_question: str = ""
    premise: str = ""
    themes: list[str] = Field(default_factory=list)
    tone: list[str] = Field(default_factory=list)
    structure: list[str] = Field(default_factory=list)


class ProseArtifact(_Strict):
    """A single block of prose (premise, pitch, synopsis)."""

    text: str


class HorizonEffect(_Strict):
    """One point on the consequence timeline."""

    horizon: str
    effect: str


class ConsequenceReport(_Strict):
    """What EXTREME_CONSEQUENCE_AGENT returns."""

    horizons: list[HorizonEffect] = Field(default_factory=list)
    systemic_risk: str = ""


class WorldBible(_Strict):
    """What WORLD_ARCHITECT_AGENT returns."""

    rules: list[str] = Field(default_factory=list)
    economy: str = ""
    institutions: str = ""
    technology: str = ""
    culture: str = ""
    language: str = ""
    classes: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)
    power: str = ""


class CharacterSheet(_Strict):
    """One character and the position they hold towards the system."""

    name: str
    position: str = ""
    want: str = ""
    fear: str = ""
    contradiction: str = ""


class CharacterSet(_Strict):
    """What CHARACTER_ARCHITECT_AGENT returns."""

    characters: list[CharacterSheet] = Field(default_factory=list)


class TitleProposal(_Strict):
    """One title candidate."""

    title: str
    reason: str = ""
    double_meaning: str = ""


class TitleBatch(_Strict):
    """What TITLE_AGENT returns."""

    titles: list[TitleProposal] = Field(default_factory=list)


class LoreConnection(_Strict):
    """One possible link to another work. Never a forced shared universe."""

    kind: str
    note: str = ""


class LoreReport(_Strict):
    """What LORE_CONNECTION_AGENT returns."""

    connections: list[LoreConnection] = Field(default_factory=list)
    force_shared_universe: bool = False


# --- criticism and judgement ------------------------------------------------


class Critique(_Strict):
    """The universal critic answer. Every evaluating agent returns this shape."""

    verdict: str = "NEUTRAL"
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    confidence: float = 50.0

    # Optional enrichments used by specific critics.
    closest_pattern: str = ""
    what_is_new: str = ""
    human_stakes: list[str] = Field(default_factory=list)
    localized_details: list[str] = Field(default_factory=list)
    pitch_line: str = ""
    audience: str = ""


class Judgement(_Strict):
    """What CREATIVE_JUDGE_AGENT returns. It judges; it never rewrites."""

    decision: str = "REJECT"
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    confidence: float = 50.0

    @property
    def approves(self) -> bool:
        """Whether the judge approved."""
        return self.decision.strip().upper() == "APPROVE"


# --- subconscious and learning ----------------------------------------------


class DreamReport(_Strict):
    """What DREAM_AGENT returns. No plausibility filter applies here."""

    fragments: list[str] = Field(default_factory=list)
    strangeness: float = 50.0
    notes: str = ""


class MutationResult(_Strict):
    """What MUTATION_AGENT returns: a structurally different idea, not a rewrite."""

    title: str
    logline: str = ""
    premise: str = ""
    central_question: str = ""
    changed_dimension: str = ""
    rationale: str = ""
    themes: list[str] = Field(default_factory=list)


class PrincipleItem(_Strict):
    """A learned principle, distinct from a raw event."""

    summary: str
    detail: str = ""
    tags: list[str] = Field(default_factory=list)


class ConsolidationReport(_Strict):
    """What MEMORY_AGENT returns."""

    principles: list[PrincipleItem] = Field(default_factory=list)
    note: str = ""


class LearningReport(_Strict):
    """What LEARNING_AGENT returns. Only EVOLVING_DNA may be updated from this."""

    discoveries: list[str] = Field(default_factory=list)
    emergent_patterns: list[str] = Field(default_factory=list)
    promising_territories: list[str] = Field(default_factory=list)
    saturated_themes: list[str] = Field(default_factory=list)
    successful_combinations: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    reason: str = ""


class ObsessionItem(_Strict):
    """One recurring theme and the angle it was explored from."""

    theme: str
    angle: str = ""
    is_new_angle: bool = True


class ObsessionReport(_Strict):
    """What OBSESSION_AGENT returns."""

    obsessions: list[ObsessionItem] = Field(default_factory=list)
    note: str = ""


class MetaCognitionReport(_Strict):
    """What META_COGNITION_AGENT returns: are we actually thinking differently?"""

    dominant_mechanism: str = ""
    diversity_note: str = ""
    recommendation: str = ""
    risk: str = ""


def json_schema_of(model: type[BaseModel]) -> dict[str, Any]:
    """The JSON schema handed to providers that support structured output."""
    return model.model_json_schema()
