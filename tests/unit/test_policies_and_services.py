"""Mutation, DNA evolution, memory, constitution, autonomy, exploration and measurement."""

from __future__ import annotations

import pytest

from creative_brain.domain.entities.agent_opinion import AgentOpinion, Verdict
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import MemoryKind, MemoryRecord, Obsession
from creative_brain.domain.exceptions import (
    AutonomyBoundaryViolation,
    DomainRuleViolation,
    ImmutableCoreDnaViolation,
)
from creative_brain.domain.policies.autonomy import (
    AutonomyPolicy,
    CreativeAction,
    RestrictedAction,
)
from creative_brain.domain.policies.constitution import ARTICLES, ConstitutionPolicy
from creative_brain.domain.policies.dna_evolution import DnaEvolutionPolicy, ProtectedAsset
from creative_brain.domain.policies.exploration import ExplorationPolicy
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.policies.memory_policy import MemoryPolicy
from creative_brain.domain.policies.mutation import MutationOperator, MutationPolicy
from creative_brain.domain.services.evaluation import (
    CreativeDistanceService,
    NoveltyService,
    SaturationService,
)
from creative_brain.domain.services.similarity import jaccard, similarity, tokenize
from creative_brain.domain.value_objects.creative_distance import CreativeZone
from creative_brain.domain.value_objects.dna import EvolvingDna
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId, MemoryId
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard, ScoreCriterion


def concept(token="aaaa1111", stage=CreativeStage.SEED, potential=80.0) -> CreativeConcept:
    c = CreativeConcept.germinate(
        concept_id=ConceptId.from_token(token),
        title="Ideia",
        logline="uma premissa qualquer",
        origin=GenomeOrigin(mechanism=OriginMechanism.INVERSION),
        at="now",
    )
    c.pull_events()
    c.stage = stage
    c.mutation_potential = potential
    return c


class TestExplorationPolicy:
    def test_allocation_must_sum_to_one(self):
        with pytest.raises(DomainRuleViolation):
            ExplorationPolicy(comfort=0.5, edge=0.5, unknown=0.5)

    def test_allocation_never_loses_a_slot_to_rounding(self):
        for total in (1, 7, 13, 100, 999):
            allocation = ExplorationPolicy().allocate(total)
            assert sum(allocation.values()) == total

    def test_default_allocation_matches_the_documented_strategy(self):
        allocation = ExplorationPolicy().allocate(100)
        assert allocation[CreativeZone.COMFORT_ZONE] == 30
        assert allocation[CreativeZone.EDGE_ZONE] == 50
        assert allocation[CreativeZone.UNKNOWN_ZONE] == 20

    def test_disabling_the_unknown_zone_redistributes_its_share(self):
        policy = ExplorationPolicy.from_mapping(
            {"comfort": 0.3, "edge": 0.5, "unknown": 0.2}, unknown_enabled=False
        )
        assert policy.unknown == 0.0
        assert policy.comfort + policy.edge == pytest.approx(1.0)

    def test_zero_slots_allocates_nothing(self):
        assert sum(ExplorationPolicy().allocate(0).values()) == 0


class TestMutationPolicy:
    def test_only_dead_ideas_may_mutate(self):
        policy = MutationPolicy()
        assert not policy.is_mutable(concept(stage=CreativeStage.CONCEPT))
        assert policy.is_mutable(concept(stage=CreativeStage.REJECTED))

    def test_weak_ideas_are_left_alone(self):
        policy = MutationPolicy(min_mutation_potential=50.0)
        assert not policy.is_mutable(concept(stage=CreativeStage.REJECTED, potential=10.0))

    def test_lineage_depth_is_capped(self):
        policy = MutationPolicy(max_lineage_depth=2)
        deep = concept(stage=CreativeStage.REJECTED)
        for index in range(3):
            deep.record_mutation(at="now", operator="invert_rule", parent_id=f"concept_p{index}")
        assert not policy.is_mutable(deep)

    def test_the_disabled_flag_stops_everything(self):
        assert not MutationPolicy(enabled=False).is_mutable(concept(stage=CreativeStage.REJECTED))

    def test_ranking_prefers_the_most_promising(self):
        policy = MutationPolicy()
        pool = [
            concept("aaaa1111", CreativeStage.REJECTED, 90.0),
            concept("bbbb2222", CreativeStage.REJECTED, 45.0),
            concept("cccc3333", CreativeStage.CONCEPT, 99.0),
        ]
        ranked = policy.rank(pool)
        assert [c.mutation_potential for c in ranked] == [90.0, 45.0]

    def test_every_operator_has_an_instruction(self):
        policy = MutationPolicy()
        for operator in MutationOperator:
            assert policy.instruction_for(operator).strip()


class TestDnaEvolutionPolicy:
    def test_core_dna_is_never_writable(self):
        with pytest.raises(ImmutableCoreDnaViolation):
            DnaEvolutionPolicy().assert_writable("CORE_DNA")

    @pytest.mark.parametrize(
        "asset",
        ["CREATIVE_CONSTITUTION", "SECURITY_POLICY", "SOURCE_CODE", "REPOSITORY_PERMISSIONS"],
    )
    def test_protected_assets_are_refused(self, asset):
        with pytest.raises(AutonomyBoundaryViolation):
            DnaEvolutionPolicy().assert_writable(asset)

    def test_evolving_dna_is_writable(self):
        DnaEvolutionPolicy().assert_writable("EVOLVING_DNA")  # must not raise

    def test_learning_is_capped_per_cycle(self):
        policy = DnaEvolutionPolicy(max_new_entries_per_cycle=2)
        updated = policy.apply(EvolvingDna(), discoveries=("a", "b", "c", "d"), reason="test")
        assert len(updated.discoveries) == 2

    def test_a_disabled_policy_changes_nothing(self):
        policy = DnaEvolutionPolicy(enabled=False)
        original = EvolvingDna()
        assert policy.apply(original, discoveries=("a",)) is original

    def test_weight_drift_is_bounded(self):
        policy = DnaEvolutionPolicy(max_weight_drift=0.05)
        assert policy.clamp_weight(0.20, 0.90) == pytest.approx(0.25)
        assert policy.clamp_weight(0.20, 0.00) == pytest.approx(0.15)

    def test_every_protected_asset_is_enumerated(self):
        assert ProtectedAsset.CORE_DNA in DnaEvolutionPolicy().protected


class TestMemoryPolicy:
    def test_principles_never_decay(self):
        policy = MemoryPolicy()
        principle = MemoryRecord(
            id=MemoryId.from_token("aaaa1111"),
            kind=MemoryKind.SEMANTIC,
            summary="p",
            created_at="now",
            is_principle=True,
            salience=50.0,
        )
        policy.decay(principle)
        assert principle.salience == 50.0

    def test_episodic_records_fade(self):
        policy = MemoryPolicy(episodic_decay_per_cycle=0.5)
        record = MemoryRecord(
            id=MemoryId.from_token("aaaa1111"),
            kind=MemoryKind.EPISODIC,
            summary="e",
            created_at="now",
            salience=80.0,
        )
        policy.decay(record)
        assert record.salience == 40.0

    def test_the_graveyard_is_immortal(self):
        policy = MemoryPolicy()
        buried = MemoryRecord(
            id=MemoryId.from_token("aaaa1111"),
            kind=MemoryKind.REJECTED,
            summary="r",
            created_at="now",
            salience=1.0,
        )
        assert not policy.should_decay(buried)
        assert policy.is_retrievable(buried)

    def test_one_event_is_not_a_lesson(self):
        policy = MemoryPolicy(min_events_per_principle=2)
        assert not policy.may_become_principle(1)
        assert policy.may_become_principle(2)

    def test_ranking_puts_principles_first(self):
        policy = MemoryPolicy()
        loud_event = MemoryRecord(
            id=MemoryId.from_token("aaaa1111"),
            kind=MemoryKind.EPISODIC,
            summary="evento",
            created_at="now",
            salience=99.0,
        )
        quiet_principle = MemoryRecord(
            id=MemoryId.from_token("bbbb2222"),
            kind=MemoryKind.SEMANTIC,
            summary="princípio",
            created_at="now",
            salience=10.0,
            is_principle=True,
        )
        assert policy.rank([loud_event, quiet_principle])[0] is quiet_principle


class TestConstitution:
    def test_all_fourteen_articles_are_declared(self):
        assert len(ARTICLES) == 14
        assert ConstitutionPolicy.article(9).text.startswith("Every work needs")

    def test_a_missing_central_question_is_fatal(self):
        """Article 9."""
        c = self._sound_candidate()
        c.central_question = ""
        assert any("article 9" in v for v in ConstitutionPolicy().violations(c))

    def test_no_consequences_is_fatal(self):
        """Article 4."""
        c = self._sound_candidate(depth=10.0)
        assert any("article 4" in v for v in ConstitutionPolicy().violations(c))

    def test_technology_replacing_drama_is_fatal(self):
        """Article 6."""
        c = self._sound_candidate(emotional_impact=5.0)
        assert any("article 6" in v for v in ConstitutionPolicy().violations(c))

    def test_a_decision_without_evidence_is_fatal(self):
        """Article 14."""
        c = self._sound_candidate()
        c.opinions.clear()
        assert any("article 14" in v for v in ConstitutionPolicy().violations(c))

    def test_a_sound_candidate_passes(self):
        assert ConstitutionPolicy().approves(self._sound_candidate())

    def _sound_candidate(self, **overrides: float) -> CreativeConcept:
        c = concept()
        c.attach("central_question", "A quem pertence a memória?")
        scores = {"depth": 70.0, "emotional_impact": 70.0, **overrides}
        c.scoreboard = ScoreBoard.from_mapping(scores)
        c.add_opinion(
            AgentOpinion(
                agent="HUMAN_DRAMA_AGENT", verdict=Verdict.SUPPORT, rationale="ok", created_at="now"
            )
        )
        return c


class TestAutonomy:
    @pytest.mark.parametrize("action", list(CreativeAction))
    def test_every_creative_action_is_autonomous(self, action):
        assert AutonomyPolicy().may(action)

    @pytest.mark.parametrize("action", list(RestrictedAction))
    def test_every_restricted_action_needs_a_human(self, action):
        policy = AutonomyPolicy()
        assert policy.requires_human(str(action))
        with pytest.raises(AutonomyBoundaryViolation):
            policy.assert_not_restricted(str(action))

    def test_approving_a_project_needs_no_human(self):
        """There is no WAIT_FOR_HUMAN_APPROVAL in the creative loop."""
        AutonomyPolicy().assert_allowed(CreativeAction.APPROVE_PROJECT)
        AutonomyPolicy().assert_allowed(CreativeAction.DECIDE_SCHEDULE)

    def test_publishing_is_never_autonomous(self):
        assert AutonomyPolicy().requires_human("publish_externally")
        assert AutonomyPolicy().requires_human("change_repository_visibility")

    def test_a_disabled_creative_action_is_refused(self):
        policy = AutonomyPolicy(autonomous=frozenset({CreativeAction.OBSERVE}))
        with pytest.raises(AutonomyBoundaryViolation):
            policy.assert_allowed(CreativeAction.DREAM)


class TestSimilarityAndMeasurement:
    def test_tokenizing_drops_stopwords_and_accents(self):
        tokens = tokenize("A memória do cartório e a herança")
        assert "memoria" in tokens
        assert "do" not in tokens

    def test_identical_texts_are_maximally_similar(self):
        assert similarity("cartório de memória", "cartório de memória") == pytest.approx(1.0)

    def test_unrelated_texts_are_dissimilar(self):
        assert similarity("cartório de memória", "peixes elétricos no deserto") < 0.15

    def test_jaccard_ignores_word_order(self):
        assert jaccard("memória herdada", "herdada memória") == pytest.approx(1.0)

    def test_empty_text_is_never_similar(self):
        assert similarity("", "qualquer coisa") == 0.0

    def test_novelty_is_the_inverse_of_the_closest_match(self):
        service = NoveltyService()
        assessment = service.assess(
            "um cartório que registra memória",
            {"c1": "um cartório que registra memória", "c2": "peixes no deserto"},
        )
        assert assessment.is_duplicate
        assert assessment.closest_id == "c1"
        assert assessment.novelty.value < 10

    def test_an_empty_corpus_means_high_novelty(self):
        assert NoveltyService().assess("qualquer ideia", {}).novelty.value == 85.0

    def test_duplicate_rate_counts_the_batch_against_itself(self):
        service = NoveltyService()
        text = "cartório registra memória como patrimônio"
        assert service.duplicate_rate([text, text, "algo totalmente diferente"]) > 0.5
        assert service.duplicate_rate(["só uma"]) == 0.0

    def test_distance_is_measured_against_the_dna(self):
        service = CreativeDistanceService()
        vocabulary = ("cartório", "memória", "herança")
        near = service.measure("um cartório de memória e herança", vocabulary)
        far = service.measure("peixes elétricos navegam no deserto de vidro", vocabulary)
        assert near.value < far.value

    def test_the_canon_makes_distance_stricter(self):
        service = CreativeDistanceService()
        text = "um cartório que registra memória"
        without = service.measure(text, ("nada a ver",)).value
        with_canon = service.measure_against_canon(
            text, ("nada a ver",), {"p1": "um cartório que registra memória"}
        ).value
        assert with_canon < without


class TestSaturation:
    def test_a_repeated_theme_without_new_angles_saturates(self):
        obsession = Obsession(theme="identidade")
        for _ in range(10):
            obsession.observe("vigilância", at="now")
        assert obsession.is_repetition

    def test_a_theme_explored_from_new_angles_is_an_obsession(self):
        obsession = Obsession(theme="memória")
        for angle in ("propriedade", "herança", "dívida", "consentimento", "luto"):
            obsession.observe(angle, at="now")
        assert not obsession.is_repetition

    def test_a_single_appearance_never_saturates(self):
        obsession = Obsession(theme="x")
        obsession.observe("a", at="now")
        assert obsession.saturation == 0.0

    def test_saturated_themes_are_reported(self):
        service = SaturationService()
        obsessions = service.build(
            {"identidade": ["vigilância"] * 10, "memória": ["propriedade", "herança", "luto"]},
            at="now",
        )
        assert "identidade" in service.saturated_themes(obsessions)
        assert "memória" not in service.saturated_themes(obsessions)

    def test_a_new_angle_is_recognised(self):
        service = SaturationService()
        assert service.is_new_angle(["vigilância do estado"], "herança de obrigações")
        assert not service.is_new_angle(["vigilância do estado"], "vigilância do estado")

    def test_unexplored_vocabulary_is_surfaced(self):
        service = SaturationService()
        unused = service.unexplored_terms(
            ["um cartório que registra memória"], ["cartório", "condomínio", "sindicato"]
        )
        assert "condomínio" in unused
        assert "cartório" not in unused
