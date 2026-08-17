"""Entity <-> JSON mapping.

Kept in the adapter layer on purpose: the domain does not know that JSON, a
filesystem or any storage format exists. ``as_dict`` on the entities is a
convenience for humans reading artifacts; rebuilding is this module's job.
"""

from __future__ import annotations

from typing import Any

from creative_brain.domain.entities.agent_opinion import AgentOpinion, DecisionTrace, Verdict
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import Dream, MemoryKind, MemoryRecord
from creative_brain.domain.entities.observation import (
    CreativeObservation,
    ResearchFinding,
    SignalDomain,
    SignalKind,
)
from creative_brain.domain.entities.project import CreativeProject
from creative_brain.domain.entities.question import CreativeQuestion, CreativeSeed
from creative_brain.domain.entities.tournament import (
    CreativeTournament,
    TournamentFunnel,
    TournamentRound,
)
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.creative_distance import CreativeDistance
from creative_brain.domain.value_objects.dna import (
    CoreDna,
    DnaPrinciple,
    EvolvingDna,
    InstitutionalLens,
    InstitutionalPillar,
)
from creative_brain.domain.value_objects.genome import CreativeGenome, GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import (
    ConceptId,
    DreamId,
    FindingId,
    MemoryId,
    ObservationId,
    ProjectId,
    QuestionId,
    SeedId,
    TournamentId,
)
from creative_brain.domain.value_objects.lineage import Lineage, LineageLink, LineageRelation
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard


def _strs(raw: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in raw) if isinstance(raw, list) else ()


def genome_from_dict(raw: dict[str, Any]) -> CreativeGenome:
    """Rebuild a creative genome."""
    origin_raw = raw.get("origin") or {}
    origin = GenomeOrigin(
        mechanism=OriginMechanism(origin_raw.get("mechanism", "observation")),
        observation=origin_raw.get("observation"),
        inversion=origin_raw.get("inversion"),
        paradox=origin_raw.get("paradox"),
        collision=_strs(origin_raw.get("collision")),
        research=origin_raw.get("research"),
        dream=origin_raw.get("dream"),
    )
    return CreativeGenome(
        origin=origin,
        themes=_strs(raw.get("themes")),
        tone=_strs(raw.get("tone")),
        structure=_strs(raw.get("structure")),
        creative_distance=CreativeDistance.clamped(float(raw.get("creative_distance", 50.0))),
        novelty_score=CreativeScore.clamped(float(raw.get("novelty_score", 50.0))),
        commercial_score=CreativeScore.clamped(float(raw.get("commercial_score", 50.0))),
        identity_score=CreativeScore.clamped(float(raw.get("identity_score", 50.0))),
    )


def opinion_from_dict(raw: dict[str, Any]) -> AgentOpinion:
    """Rebuild an agent opinion."""
    return AgentOpinion(
        agent=str(raw.get("agent", "")),
        verdict=Verdict(raw.get("verdict", "NEUTRAL")),
        rationale=str(raw.get("rationale", "")),
        created_at=str(raw.get("created_at", "")),
        scores=ScoreBoard.from_mapping(raw.get("scores") or {}),
        evidence=_strs(raw.get("evidence")),
        confidence=float(raw.get("confidence", 50.0)),
    )


def concept_from_dict(raw: dict[str, Any]) -> CreativeConcept:
    """Rebuild a full concept aggregate, including lineage and opinions."""
    lineage = Lineage(
        tuple(
            LineageLink(
                relation=LineageRelation(link.get("relation", "derived_from")),
                ancestor_id=str(link.get("ancestor_id", "")),
                note=str(link.get("note", "")),
            )
            for link in raw.get("lineage") or []
        )
    )
    concept = CreativeConcept(
        id=ConceptId(str(raw["id"])),
        title=str(raw.get("title", "")),
        logline=str(raw.get("logline", "")),
        genome=genome_from_dict(raw.get("genome") or {}),
        created_at=str(raw.get("created_at", "")),
        updated_at=str(raw.get("updated_at", "")),
        stage=CreativeStage(raw.get("stage", "SEED")),
        cycle_id=str(raw.get("cycle_id", "")),
        seed_id=str(raw.get("seed_id", "")),
        question_id=str(raw.get("question_id", "")),
        central_question=str(raw.get("central_question", "")),
        themes=_strs(raw.get("themes")),
        lineage=lineage,
        scoreboard=ScoreBoard.from_mapping(raw.get("scores") or {}),
        opinions=[opinion_from_dict(o) for o in raw.get("opinions") or []],
        artifacts=dict(raw.get("artifacts") or {}),
        rejection_reasons=_strs(raw.get("rejection_reasons")),
        mutation_potential=float(raw.get("mutation_potential", 50.0)),
        total_score=CreativeScore.clamped(float(raw.get("total_score", 0.0))),
        rejected_at=str(raw.get("rejected_at", "")),
    )
    return concept


def observation_from_dict(raw: dict[str, Any]) -> CreativeObservation:
    """Rebuild an observation."""
    return CreativeObservation(
        id=ObservationId(str(raw["id"])),
        statement=str(raw.get("statement", "")),
        domain=SignalDomain(raw.get("domain", "society")),
        kind=SignalKind(raw.get("kind", "fact")),
        captured_at=str(raw.get("captured_at", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        source=str(raw.get("source", "internal_observer")),
        tension=str(raw.get("tension", "")),
        tags=_strs(raw.get("tags")),
        salience=float(raw.get("salience", 50.0)),
    )


def finding_from_dict(raw: dict[str, Any]) -> ResearchFinding:
    """Rebuild a research finding."""
    return ResearchFinding(
        id=FindingId(str(raw["id"])),
        topic=str(raw.get("topic", "")),
        summary=str(raw.get("summary", "")),
        created_at=str(raw.get("created_at", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        observation_id=str(raw.get("observation_id", "")),
        key_facts=_strs(raw.get("key_facts")),
        implications=_strs(raw.get("implications")),
        sources=_strs(raw.get("sources")),
        confidence=float(raw.get("confidence", 50.0)),
        provider=str(raw.get("provider", "offline")),
        tags=_strs(raw.get("tags")),
    )


def question_from_dict(raw: dict[str, Any]) -> CreativeQuestion:
    """Rebuild a creative question."""
    return CreativeQuestion(
        id=QuestionId(str(raw["id"])),
        text=str(raw.get("text", "")),
        created_at=str(raw.get("created_at", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        observation_id=str(raw.get("observation_id", "")),
        provocation=str(raw.get("provocation", "")),
        depth=int(raw.get("depth", 1)),
        tags=_strs(raw.get("tags")),
        answered_by=_strs(raw.get("answered_by")),
    )


def seed_from_dict(raw: dict[str, Any]) -> CreativeSeed:
    """Rebuild a creative seed."""
    origin_raw = raw.get("origin") or {}
    return CreativeSeed(
        id=SeedId(str(raw["id"])),
        statement=str(raw.get("statement", "")),
        created_at=str(raw.get("created_at", "")),
        origin=GenomeOrigin(
            mechanism=OriginMechanism(origin_raw.get("mechanism", "observation")),
            observation=origin_raw.get("observation"),
            inversion=origin_raw.get("inversion"),
            paradox=origin_raw.get("paradox"),
            collision=_strs(origin_raw.get("collision")),
            research=origin_raw.get("research"),
            dream=origin_raw.get("dream"),
        ),
        cycle_id=str(raw.get("cycle_id", "")),
        question_id=str(raw.get("question_id", "")),
        observation_id=str(raw.get("observation_id", "")),
        tags=_strs(raw.get("tags")),
        heat=float(raw.get("heat", 50.0)),
    )


def memory_from_dict(raw: dict[str, Any]) -> MemoryRecord:
    """Rebuild a memory record."""
    return MemoryRecord(
        id=MemoryId(str(raw["id"])),
        kind=MemoryKind(raw.get("kind", "episodic")),
        summary=str(raw.get("summary", "")),
        created_at=str(raw.get("created_at", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        subject_id=str(raw.get("subject_id", "")),
        detail=str(raw.get("detail", "")),
        tags=_strs(raw.get("tags")),
        salience=float(raw.get("salience", 50.0)),
        is_principle=bool(raw.get("is_principle", False)),
        source_events=_strs(raw.get("source_events")),
    )


def dream_from_dict(raw: dict[str, Any]) -> Dream:
    """Rebuild a dream session."""
    return Dream(
        id=DreamId(str(raw["id"])),
        started_at=str(raw.get("started_at", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        finished_at=str(raw.get("finished_at", "")),
        fragments=_strs(raw.get("fragments")),
        resurrected_ids=_strs(raw.get("resurrected_ids")),
        harvested_seed_ids=_strs(raw.get("harvested_seed_ids")),
        strangeness=float(raw.get("strangeness", 0.0)),
        notes=str(raw.get("notes", "")),
    )


def tournament_from_dict(raw: dict[str, Any]) -> CreativeTournament:
    """Rebuild a tournament with its rounds."""
    funnel = TournamentFunnel.from_pairs(
        [(step["stage"], int(step["survivors"])) for step in raw.get("funnel") or []]
    )
    tournament = CreativeTournament(
        id=TournamentId(str(raw["id"])),
        cycle_id=str(raw.get("cycle_id", "")),
        funnel=funnel,
        started_at=str(raw.get("started_at", "")),
        entrants=_strs(raw.get("entrants")),
        winner_id=str(raw.get("winner_id", "")),
        finished_at=str(raw.get("finished_at", "")),
        diversity_score=float(raw.get("diversity_score", 0.0)),
    )
    tournament.rounds = [
        TournamentRound(
            stage=CreativeStage(round_["stage"]),
            entrants=_strs(round_.get("entrants")),
            survivors=_strs(round_.get("survivors")),
            eliminated=_strs(round_.get("eliminated")),
            finished_at=str(round_.get("finished_at", "")),
        )
        for round_ in raw.get("rounds") or []
    ]
    return tournament


def project_from_dict(raw: dict[str, Any]) -> CreativeProject:
    """Rebuild an approved project."""
    scores = dict(raw.get("creative_scores") or {})
    total = float(scores.pop("total", 0.0))
    project = CreativeProject(
        id=ProjectId(str(raw["project_id"])),
        concept_id=str(raw.get("concept_id", "")),
        title=str(raw.get("title", "")),
        logline=str(raw.get("logline", "")),
        central_question=str(raw.get("central_question", "")),
        genome=genome_from_dict(raw.get("creative_genome") or {}),
        created_at=str(raw.get("created_at", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        status=str(raw.get("status", "APPROVED")),
        scoreboard=ScoreBoard.from_mapping(scores),
        total_score=total,
        artifacts=dict(raw.get("artifact_bodies") or {}),
        recommended_engines=_strs(raw.get("recommended_engines")),
    )
    project.decision_traces = [
        DecisionTrace(
            who=str(t.get("who", "")),
            what=str(t.get("what", "")),
            why=str(t.get("why", "")),
            decided_at=str(t.get("decided_at", "")),
            inputs=_strs(t.get("inputs")),
            scores={k: float(v) for k, v in (t.get("scores") or {}).items()},
            evidence=_strs(t.get("evidence")),
            cycle_id=str(t.get("cycle_id", "")),
            correlation_id=str(t.get("correlation_id", "")),
        )
        for t in raw.get("decision_traces") or []
    ]
    return project


def core_dna_from_dict(raw: dict[str, Any]) -> CoreDna:
    """Rebuild the protected DNA tier."""
    return CoreDna(
        identity=str(raw.get("identity", "")),
        philosophy=_strs(raw.get("philosophy")),
        principles=tuple(
            DnaPrinciple(
                key=str(p.get("key", "")),
                statement=str(p.get("statement", "")),
                category=str(p.get("category", "general")),
                weight=float(p.get("weight", 1.0)),
            )
            for p in raw.get("principles") or []
        ),
        narrative_patterns=_strs(raw.get("narrative_patterns")),
        aesthetics=_strs(raw.get("aesthetics")),
        signature_mechanisms=_strs(raw.get("signature_mechanisms")),
        forbidden_moves=_strs(raw.get("forbidden_moves")),
        institutional_lenses=_lenses_from_dict(raw.get("institutional_lenses") or {}),
    )


def _lenses_from_dict(raw: dict[str, Any]) -> dict[str, InstitutionalLens]:
    """Parse the ``institutional_lenses`` block of CORE_DNA."""
    result: dict[str, InstitutionalLens] = {}
    for key, data in raw.items():
        pillars = tuple(
            InstitutionalPillar(
                key=str(p.get("key", "")),
                statement=str(p.get("statement", "")),
                creative_application=str(p.get("creative_application", "")),
            )
            for p in data.get("pillars") or []
        )
        result[key] = InstitutionalLens(
            label=str(data.get("label", key)),
            purpose=str(data.get("purpose", "")),
            pillars=pillars,
        )
    return result


def evolving_dna_from_dict(raw: dict[str, Any]) -> EvolvingDna:
    """Rebuild the learned DNA tier."""
    return EvolvingDna(
        version=int(raw.get("version", 0)),
        discoveries=_strs(raw.get("discoveries")),
        emergent_patterns=_strs(raw.get("emergent_patterns")),
        promising_territories=_strs(raw.get("promising_territories")),
        saturated_themes=_strs(raw.get("saturated_themes")),
        successful_combinations=_strs(raw.get("successful_combinations")),
        techniques=_strs(raw.get("techniques")),
        updated_at=str(raw.get("updated_at", "")),
        change_log=_strs(raw.get("change_log")),
    )
