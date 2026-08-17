"""Use cases for the OBSERVATION and HUNT phases."""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.agents.schemas import ObservationBatch, QuestionBatch, ResearchReport
from creative_brain.application.context import BrainContext
from creative_brain.domain.entities.observation import (
    CreativeObservation,
    ResearchFinding,
    SignalDomain,
    SignalKind,
)
from creative_brain.domain.entities.question import CreativeQuestion
from creative_brain.domain.events import DomainEvent, EventName
from creative_brain.domain.exceptions import ResearchFailure
from creative_brain.domain.value_objects.identifiers import FindingId, ObservationId, QuestionId
from creative_brain.ports.outbound.knowledge import ResearchQuery


@dataclass
class CaptureObservation:
    """Ask OBSERVER_AGENT for signals and persist them.

    The observer is deliberately forbidden from writing stories: everything it
    produces is raw material other agents must transform.
    """

    context: BrainContext

    def execute(self, *, cycle_id: str, focus: str = "") -> list[CreativeObservation]:
        """Capture a batch of observations for the current cycle."""
        ctx = self.context
        agent = ctx.society.get("OBSERVER_AGENT")
        recent = ctx.repositories.observations.recent(limit=10)
        batch: ObservationBatch = agent.run(
            variables={
                "count": str(ctx.targets.observations),
                "focus": focus or "(no focus set yet)",
                "recent_themes": ", ".join(sorted({t for o in recent for t in o.tags})) or "(none)",
            },
            hints={"count": str(ctx.targets.observations)},
            fallback=ObservationBatch(),
        )

        captured: list[CreativeObservation] = []
        for item in batch.observations:
            if not item.statement.strip():
                continue
            observation = CreativeObservation(
                id=ctx.new_id(ObservationId),
                statement=item.statement,
                domain=_enum(SignalDomain, item.domain, SignalDomain.SOCIETY),
                kind=_enum(SignalKind, item.kind, SignalKind.FACT),
                captured_at=ctx.now(),
                cycle_id=cycle_id,
                source="OBSERVER_AGENT",
                tension=item.tension,
                tags=tuple(item.tags),
                salience=float(item.salience),
            )
            ctx.repositories.observations.add(observation)
            ctx.vectors.index(
                str(observation.id), observation.statement, {"kind": "observation"}
            )
            ctx.bus.publish(
                DomainEvent(
                    name=EventName.OBSERVATION_CAPTURED,
                    occurred_at=observation.captured_at,
                    cycle_id=cycle_id,
                    subject_id=str(observation.id),
                    agent_id="OBSERVER_AGENT",
                    correlation_id=ctx.correlation_id,
                    payload={"statement": observation.statement, "domain": str(observation.domain)},
                )
            )
            captured.append(observation)

        ctx.metrics.increment("observations_captured", float(len(captured)))
        ctx.logger.info("phase.observation", captured=len(captured), cycle_id=cycle_id)
        return captured


@dataclass
class RunResearch:
    """Investigate the most salient observations through the research port."""

    context: BrainContext

    def execute(self, *, cycle_id: str) -> list[ResearchFinding]:
        """Research the top topics of the cycle."""
        ctx = self.context
        observations = sorted(
            ctx.repositories.observations.list_for_cycle(cycle_id),
            key=lambda o: o.salience,
            reverse=True,
        )[: ctx.targets.research_topics]
        if not observations:
            return []

        findings: list[ResearchFinding] = []
        for observation in observations:
            topic = observation.tags[0] if observation.tags else observation.statement[:60]
            try:
                result = ctx.research.investigate(
                    ResearchQuery(topic=topic, depth=1, context=observation.statement)
                )
            except ResearchFailure as exc:
                ctx.logger.warning("research.failed", topic=topic, error=str(exc))
                ctx.metrics.increment("research_failures")
                continue

            finding = ResearchFinding(
                id=ctx.new_id(FindingId),
                topic=topic,
                summary=result.summary,
                created_at=ctx.now(),
                cycle_id=cycle_id,
                observation_id=str(observation.id),
                key_facts=result.key_facts,
                implications=result.implications,
                sources=result.sources,
                confidence=result.confidence,
                provider=result.provider,
                tags=observation.tags,
            )
            ctx.repositories.research.add(finding)
            ctx.vectors.index(str(finding.id), f"{finding.topic} {finding.summary}", {"kind": "research"})
            ctx.metrics.increment("research_calls")
            ctx.bus.publish(
                DomainEvent(
                    name=EventName.RESEARCH_COMPLETED,
                    occurred_at=finding.created_at,
                    cycle_id=cycle_id,
                    subject_id=str(finding.id),
                    agent_id="RESEARCH_AGENT",
                    correlation_id=ctx.correlation_id,
                    payload={"topic": topic, "provider": result.provider},
                )
            )
            findings.append(finding)

        ctx.logger.info("phase.hunt", findings=len(findings), cycle_id=cycle_id)
        return findings


@dataclass
class GenerateCreativeQuestions:
    """Turn observations into questions. Questions outlive the ideas that fail them."""

    context: BrainContext

    def execute(self, *, cycle_id: str) -> list[CreativeQuestion]:
        """Ask CURIOSITY_AGENT for questions about this cycle's observations."""
        ctx = self.context
        agent = ctx.society.get("CURIOSITY_AGENT")
        observations = ctx.repositories.observations.list_for_cycle(cycle_id)
        if not observations:
            return []

        questions: list[CreativeQuestion] = []
        for observation in observations[: ctx.targets.observations]:
            batch: QuestionBatch = agent.run(
                variables={
                    "observation": observation.statement,
                    "count": str(ctx.targets.questions_per_observation),
                },
                hints={
                    "count": str(ctx.targets.questions_per_observation),
                    "observation": observation.statement,
                },
                fallback=QuestionBatch(),
            )
            for item in batch.questions:
                if not item.text.strip():
                    continue
                question = CreativeQuestion(
                    id=ctx.new_id(QuestionId),
                    text=item.text,
                    created_at=ctx.now(),
                    cycle_id=cycle_id,
                    observation_id=str(observation.id),
                    provocation=item.provocation or observation.statement,
                    tags=tuple(item.tags) or observation.tags,
                )
                ctx.repositories.questions.add(question)
                ctx.bus.publish(
                    DomainEvent(
                        name=EventName.QUESTION_GENERATED,
                        occurred_at=question.created_at,
                        cycle_id=cycle_id,
                        subject_id=str(question.id),
                        agent_id="CURIOSITY_AGENT",
                        correlation_id=ctx.correlation_id,
                        payload={"text": question.text},
                    )
                )
                questions.append(question)

        ctx.metrics.increment("questions_generated", float(len(questions)))
        ctx.logger.info("phase.focus.questions", questions=len(questions), cycle_id=cycle_id)
        return questions


def _enum(enum_type, raw: str, default):  # noqa: ANN001, ANN202 - tiny generic coercion helper
    """Coerce a model's free-text enum value, falling back when it is unknown."""
    try:
        return enum_type(str(raw).strip().lower())
    except ValueError:
        return default


__all__ = ["CaptureObservation", "GenerateCreativeQuestions", "RunResearch"]
