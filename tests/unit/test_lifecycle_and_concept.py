"""The state machine and the CreativeConcept aggregate."""

from __future__ import annotations

import pytest

from creative_brain.domain.entities.agent_opinion import AgentOpinion, Verdict
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.events import EventName
from creative_brain.domain.exceptions import DomainRuleViolation, InvalidStateTransition
from creative_brain.domain.policies.lifecycle import (
    ADVANCING_ORDER,
    REVIVABLE_STAGES,
    CreativeStage,
    allowed_targets,
    can_transition,
    is_alive,
    is_terminal,
    next_stage,
)
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard, ScoreCriterion

ORIGIN = GenomeOrigin(mechanism=OriginMechanism.PARADOX, paradox="pobreza premium")


def make_concept(stage: CreativeStage = CreativeStage.SEED, **kwargs) -> CreativeConcept:
    concept = CreativeConcept.germinate(
        concept_id=ConceptId.from_token(kwargs.pop("token", "abcd1234")),
        title=kwargs.pop("title", "Certidão de Ausência"),
        logline=kwargs.pop("logline", "Uma regra nova aplicada corretamente destrói uma família."),
        origin=ORIGIN,
        at="2026-01-01T06:00:00Z",
        cycle_id="cycle_test0001",
        **kwargs,
    )
    concept.pull_events()
    while concept.stage is not stage and concept.stage in ADVANCING_ORDER:
        if stage not in ADVANCING_ORDER:
            break
        if ADVANCING_ORDER.index(concept.stage) >= ADVANCING_ORDER.index(stage):
            break
        concept.advance_to(next_stage(concept.stage), at="2026-01-01T07:00:00Z")
    concept.pull_events()
    return concept


class TestStateMachine:
    def test_main_line_is_walkable_end_to_end(self):
        stage = CreativeStage.SEED
        for expected in ADVANCING_ORDER[1:]:
            assert can_transition(stage, expected), f"{stage} -> {expected} should be allowed"
            stage = expected
        assert stage is CreativeStage.PRODUCTION_READY

    def test_cannot_skip_stages(self):
        assert not can_transition(CreativeStage.SEED, CreativeStage.CANDIDATE)
        assert not can_transition(CreativeStage.CONCEPT, CreativeStage.APPROVED)

    def test_production_ready_is_terminal(self):
        assert is_terminal(CreativeStage.PRODUCTION_READY)
        assert allowed_targets(CreativeStage.PRODUCTION_READY) == frozenset()

    def test_a_grave_is_never_emptied_back_onto_the_main_line(self):
        """Resurrection copies into MUTATION_POOL; the buried record stays buried."""
        assert allowed_targets(CreativeStage.GRAVEYARD) == frozenset(
            {CreativeStage.MUTATION_POOL}
        )
        assert not can_transition(CreativeStage.GRAVEYARD, CreativeStage.CONCEPT)

    def test_approved_cannot_be_rejected(self):
        assert not can_transition(CreativeStage.APPROVED, CreativeStage.REJECTED)

    def test_revivable_stages_are_off_the_main_line(self):
        assert not any(is_alive(stage) for stage in REVIVABLE_STAGES)

    def test_next_stage_refuses_past_the_end(self):
        with pytest.raises(InvalidStateTransition):
            next_stage(CreativeStage.PRODUCTION_READY)

    def test_next_stage_refuses_off_line_stages(self):
        with pytest.raises(InvalidStateTransition):
            next_stage(CreativeStage.GRAVEYARD)


class TestCreativeConcept:
    def test_germination_emits_an_event(self):
        concept = CreativeConcept.germinate(
            concept_id=ConceptId.from_token("abcd1234"),
            title="Título",
            logline="logline",
            origin=ORIGIN,
            at="2026-01-01T06:00:00Z",
        )
        events = concept.pull_events()
        assert [e.name for e in events] == [EventName.CONCEPT_CREATED]

    def test_a_concept_cannot_exist_without_a_title(self):
        with pytest.raises(DomainRuleViolation):
            CreativeConcept.germinate(
                concept_id=ConceptId.from_token("abcd1234"),
                title="   ",
                logline="x",
                origin=ORIGIN,
                at="now",
            )

    def test_illegal_transition_raises(self):
        concept = make_concept()
        with pytest.raises(InvalidStateTransition):
            concept.advance_to(CreativeStage.APPROVED, at="now")

    def test_rejection_requires_a_reason(self):
        concept = make_concept(CreativeStage.CONCEPT)
        with pytest.raises(DomainRuleViolation):
            concept.reject((), at="now")

    def test_rejection_preserves_why_it_died(self):
        concept = make_concept(CreativeStage.CONCEPT)
        concept.reject(("derivativo", "sem consequência"), at="2026-01-02T00:00:00Z")
        assert concept.stage is CreativeStage.REJECTED
        assert concept.rejection_reasons == ("derivativo", "sem consequência")
        assert concept.rejected_at == "2026-01-02T00:00:00Z"

    def test_resurrection_copies_and_leaves_the_original_buried(self):
        concept = make_concept(CreativeStage.CONCEPT)
        concept.reject(("fraco",), at="now")
        concept.entomb(at="now")
        concept.pull_events()

        revived = concept.resurrect_as(
            concept_id=ConceptId.from_token("efgh5678"),
            at="later",
            note="sonho",
            cycle_id="cycle_test0002",
        )
        assert concept.stage is CreativeStage.GRAVEYARD
        assert revived.stage is CreativeStage.MUTATION_POOL
        assert revived.lineage.has_ancestor(str(concept.id))
        assert [e.name for e in revived.pull_events()] == [EventName.IDEA_RESURRECTED]

    def test_a_confident_rejection_blocks_the_concept(self):
        concept = make_concept()
        concept.add_opinion(
            AgentOpinion(
                agent="RED_TEAM_AGENT",
                verdict=Verdict.REJECT,
                rationale="quebra no segundo ato",
                created_at="now",
                confidence=85.0,
            )
        )
        assert concept.is_blocked

    def test_a_hesitant_rejection_does_not_block(self):
        concept = make_concept()
        concept.add_opinion(
            AgentOpinion(
                agent="RED_TEAM_AGENT",
                verdict=Verdict.REJECT,
                rationale="talvez",
                created_at="now",
                confidence=40.0,
            )
        )
        assert not concept.is_blocked

    def test_support_ratio_ignores_abstentions(self):
        concept = make_concept()
        for agent, verdict in (
            ("A", Verdict.SUPPORT),
            ("B", Verdict.REJECT),
            ("C", Verdict.ABSTAIN),
        ):
            concept.add_opinion(
                AgentOpinion(agent=agent, verdict=verdict, rationale="", created_at="now")
            )
        assert concept.support_ratio == pytest.approx(0.5)

    def test_disagreement_peaks_at_an_even_split(self):
        concept = make_concept()
        concept.add_opinion(
            AgentOpinion(agent="A", verdict=Verdict.SUPPORT, rationale="", created_at="now")
        )
        assert concept.disagreement == 0.0
        concept.add_opinion(
            AgentOpinion(agent="B", verdict=Verdict.REJECT, rationale="", created_at="now")
        )
        assert concept.disagreement == 1.0

    def test_opinions_feed_the_scoreboard(self):
        concept = make_concept()
        concept.add_opinion(
            AgentOpinion(
                agent="ANTI_CLICHE_AGENT",
                verdict=Verdict.NEUTRAL,
                rationale="",
                created_at="now",
                scores=ScoreBoard({ScoreCriterion.ORIGINALITY: CreativeScore(70)}),
            )
        )
        assert concept.scoreboard.get(ScoreCriterion.ORIGINALITY).value == 70.0

    def test_unknown_artifacts_are_refused(self):
        concept = make_concept()
        with pytest.raises(DomainRuleViolation):
            concept.attach("screenplay", "…")

    def test_attaching_the_central_question_promotes_it(self):
        concept = make_concept()
        concept.attach("central_question", "A quem pertence a memória?")
        assert concept.central_question == "A quem pertence a memória?"

    def test_mutation_records_lineage_and_emits(self):
        concept = make_concept()
        concept.record_mutation(at="now", operator="invert_rule", parent_id="concept_parent1")
        assert concept.lineage.has_ancestor("concept_parent1")
        assert [e.name for e in concept.pull_events()] == [EventName.CONCEPT_MUTATED]
