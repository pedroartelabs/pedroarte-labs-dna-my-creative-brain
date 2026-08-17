"""Value object invariants."""

from __future__ import annotations

import pytest

from creative_brain.domain.exceptions import (
    DomainRuleViolation,
    ImmutableCoreDnaViolation,
    InvalidCreativeDistance,
    InvalidCreativeScore,
    InvalidEnergyLevel,
)
from creative_brain.domain.value_objects.creative_distance import CreativeDistance, CreativeZone
from creative_brain.domain.value_objects.dna import CoreDna, EvolvingDna
from creative_brain.domain.value_objects.energy import EnergyKind, EnergyLevel, EnergyProfile
from creative_brain.domain.value_objects.identifiers import ConceptId, EntityId
from creative_brain.domain.value_objects.lineage import Lineage, LineageRelation
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard, ScoreCriterion


class TestCreativeScore:
    def test_accepts_the_full_range(self):
        assert CreativeScore(0).value == 0
        assert CreativeScore(100).value == 100

    @pytest.mark.parametrize("value", [-0.1, 100.1, 1000, -50])
    def test_rejects_out_of_range(self, value):
        with pytest.raises(InvalidCreativeScore):
            CreativeScore(value)

    def test_clamped_never_raises(self):
        assert CreativeScore.clamped(-20).value == 0
        assert CreativeScore.clamped(500).value == 100

    def test_rejects_nan(self):
        with pytest.raises(InvalidCreativeScore):
            CreativeScore(float("nan"))

    def test_blend_interpolates(self):
        assert CreativeScore(0).blend(CreativeScore(100), 0.5).value == 50.0
        assert CreativeScore(20).blend(CreativeScore(80), 0.0).value == 20.0

    def test_is_ordered(self):
        assert CreativeScore(10) < CreativeScore(20)


class TestScoreBoard:
    def test_missing_criteria_read_as_zero(self):
        board = ScoreBoard({ScoreCriterion.DEPTH: CreativeScore(80)})
        assert board.get(ScoreCriterion.ORIGINALITY).value == 0.0

    def test_weighted_total_normalises_by_total_weight(self):
        board = ScoreBoard(
            {ScoreCriterion.DEPTH: CreativeScore(80), ScoreCriterion.ORIGINALITY: CreativeScore(40)}
        )
        total = board.weighted_total(
            {ScoreCriterion.DEPTH: 0.5, ScoreCriterion.ORIGINALITY: 0.5}
        )
        assert total.value == pytest.approx(60.0)

    def test_weighted_total_rejects_zero_weights(self):
        with pytest.raises(InvalidCreativeScore):
            ScoreBoard({}).weighted_total({ScoreCriterion.DEPTH: 0.0})

    def test_merge_averages_overlaps_and_unions_the_rest(self):
        left = ScoreBoard({ScoreCriterion.DEPTH: CreativeScore(80)})
        right = ScoreBoard(
            {ScoreCriterion.DEPTH: CreativeScore(40), ScoreCriterion.ORIGINALITY: CreativeScore(60)}
        )
        merged = left.merge(right)
        assert merged.get(ScoreCriterion.DEPTH).value == 60.0
        assert merged.get(ScoreCriterion.ORIGINALITY).value == 60.0

    def test_from_mapping_ignores_unknown_criteria(self):
        board = ScoreBoard.from_mapping({"depth": 70, "vibes": 99})
        assert board.as_dict() == {"depth": 70.0}


class TestCreativeDistance:
    @pytest.mark.parametrize(
        ("value", "zone"),
        [
            (0, CreativeZone.COMFORT_ZONE),
            (40, CreativeZone.COMFORT_ZONE),
            (41, CreativeZone.EDGE_ZONE),
            (75, CreativeZone.EDGE_ZONE),
            (76, CreativeZone.UNKNOWN_ZONE),
            (100, CreativeZone.UNKNOWN_ZONE),
        ],
    )
    def test_zone_boundaries(self, value, zone):
        assert CreativeDistance(value).zone is zone

    def test_rejects_out_of_range(self):
        with pytest.raises(InvalidCreativeDistance):
            CreativeDistance(101)

    def test_near_copy_detection(self):
        assert CreativeDistance(5).is_near_copy
        assert not CreativeDistance(30).is_near_copy


class TestEnergy:
    def test_rejects_out_of_range(self):
        with pytest.raises(InvalidEnergyLevel):
            EnergyLevel(101)

    def test_spend_and_restore_stay_clamped(self):
        assert EnergyLevel(10).spend(50).value == 0.0
        assert EnergyLevel(90).restore(50).value == 100.0

    def test_spend_uses_absolute_value(self):
        assert EnergyLevel(50).spend(-10).value == 40.0

    def test_sleep_restores_and_relieves_pressure(self):
        tired = EnergyProfile(
            creative=EnergyLevel(10),
            research=EnergyLevel(10),
            critical=EnergyLevel(10),
            novelty_pressure=EnergyLevel(90),
            memory_pressure=EnergyLevel(90),
        )
        rested = tired.restored_by_sleep()
        assert rested.creative.value > tired.creative.value
        assert rested.memory_pressure.value < tired.memory_pressure.value

    def test_round_trips_through_a_mapping(self):
        profile = EnergyProfile(creative=EnergyLevel(42))
        assert EnergyProfile.from_mapping(profile.as_dict()).creative.value == 42.0

    def test_profile_is_immutable(self):
        original = EnergyProfile.rested()
        spent = original.spend(EnergyKind.CREATIVE, 30)
        assert original.creative.value == 100.0
        assert spent.creative.value == 70.0


class TestIdentifiers:
    def test_requires_the_right_prefix(self):
        with pytest.raises(DomainRuleViolation):
            ConceptId("seed_abcd1234")

    def test_rejects_a_malformed_token(self):
        with pytest.raises(DomainRuleViolation):
            ConceptId("concept_AB")

    def test_from_token_builds_a_valid_id(self):
        assert str(ConceptId.from_token("abcd1234")) == "concept_abcd1234"

    def test_base_class_has_its_own_prefix(self):
        assert str(EntityId.from_token("abcd")) == "entity_abcd"


class TestDna:
    def test_core_dna_refuses_to_mutate(self):
        core = CoreDna(identity="x")
        with pytest.raises(ImmutableCoreDnaViolation):
            core.mutate(identity="y")

    def test_evolving_dna_versions_on_every_change(self):
        dna = EvolvingDna()
        updated = dna.learn(discoveries=("a",), reason="test", at="now")
        assert updated.version == 1
        assert dna.version == 0  # the original is untouched

    def test_learning_deduplicates_case_insensitively(self):
        dna = EvolvingDna().learn(discoveries=("Memória",))
        again = dna.learn(discoveries=("memória", "nova"))
        assert again.discoveries == ("Memória", "nova")

    def test_saturation_lookup_is_case_insensitive(self):
        dna = EvolvingDna(saturated_themes=("Vigilância",))
        assert dna.is_saturated("vigilância")

    def test_buckets_are_capped(self):
        dna = EvolvingDna()
        for index in range(100):
            dna = dna.learn(discoveries=(f"item-{index}",))
        assert len(dna.discoveries) == EvolvingDna.MAX_ENTRIES_PER_BUCKET


class TestLineage:
    def test_records_ancestry_in_order(self):
        lineage = (
            Lineage()
            .add(LineageRelation.DERIVED_FROM, "seed_1")
            .add(LineageRelation.MUTATED_FROM, "concept_2", "invert_rule")
        )
        assert lineage.depth == 2
        assert lineage.ancestors == ("seed_1", "concept_2")
        assert lineage.has_ancestor("concept_2")

    def test_is_immutable(self):
        original = Lineage()
        original.add(LineageRelation.DERIVED_FROM, "seed_1")
        assert original.depth == 0
