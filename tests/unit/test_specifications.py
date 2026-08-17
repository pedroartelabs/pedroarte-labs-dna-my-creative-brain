"""Composable specifications used to query creative artifacts."""

from __future__ import annotations

import pytest

from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.specifications import (
    FromCycle,
    HasTheme,
    InStage,
    InZone,
    IsAlive,
    IsRevivable,
    ScoredAbove,
)
from creative_brain.domain.value_objects.creative_distance import CreativeDistance, CreativeZone
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId
from creative_brain.domain.value_objects.scores import CreativeScore


def make(
    token: str,
    *,
    stage: CreativeStage = CreativeStage.CONCEPT,
    themes: tuple[str, ...] = ("memória",),
    distance: float = 50.0,
    score: float = 60.0,
    cycle_id: str = "cycle_test0001",
) -> CreativeConcept:
    concept = CreativeConcept.germinate(
        concept_id=ConceptId.from_token(token),
        title=f"Ideia {token}",
        logline="uma premissa",
        origin=GenomeOrigin(mechanism=OriginMechanism.PARADOX),
        at="now",
        cycle_id=cycle_id,
        themes=themes,
    )
    concept.pull_events()
    concept.stage = stage
    concept.apply_evaluation(distance=CreativeDistance(distance))
    concept.apply_total(CreativeScore(score), at="now")
    return concept


@pytest.fixture
def pool() -> list[CreativeConcept]:
    return [
        make("aaaa1111", stage=CreativeStage.CONCEPT, distance=20, score=80),
        make("bbbb2222", stage=CreativeStage.REJECTED, distance=60, score=40),
        make("cccc3333", stage=CreativeStage.GRAVEYARD, distance=90, score=20, themes=("dívida",)),
        make("dddd4444", stage=CreativeStage.APPROVED, distance=55, score=95, cycle_id="cycle_other01"),
    ]


class TestBasicSpecifications:
    def test_in_stage(self, pool):
        spec = InStage(frozenset({CreativeStage.CONCEPT, CreativeStage.APPROVED}))
        assert {str(c.id) for c in spec.filter(pool)} == {"concept_aaaa1111", "concept_dddd4444"}

    def test_is_alive(self, pool):
        assert {str(c.id) for c in IsAlive().filter(pool)} == {
            "concept_aaaa1111",
            "concept_dddd4444",
        }

    def test_is_revivable(self, pool):
        assert {str(c.id) for c in IsRevivable().filter(pool)} == {
            "concept_bbbb2222",
            "concept_cccc3333",
        }

    def test_in_zone(self, pool):
        assert [str(c.id) for c in InZone(CreativeZone.COMFORT_ZONE).filter(pool)] == [
            "concept_aaaa1111"
        ]
        assert [str(c.id) for c in InZone(CreativeZone.UNKNOWN_ZONE).filter(pool)] == [
            "concept_cccc3333"
        ]

    def test_scored_above(self, pool):
        assert len(ScoredAbove(70).filter(pool)) == 2

    def test_has_theme_is_case_insensitive(self, pool):
        assert [str(c.id) for c in HasTheme("MEMÓRIA").filter(pool)] == [
            "concept_aaaa1111",
            "concept_bbbb2222",
            "concept_dddd4444",
        ]

    def test_from_cycle(self, pool):
        assert [str(c.id) for c in FromCycle("cycle_other01").filter(pool)] == [
            "concept_dddd4444"
        ]


class TestComposition:
    def test_and_requires_both(self, pool):
        spec = IsAlive() & ScoredAbove(90)
        assert [str(c.id) for c in spec.filter(pool)] == ["concept_dddd4444"]

    def test_or_accepts_either(self, pool):
        spec = InZone(CreativeZone.COMFORT_ZONE) | InZone(CreativeZone.UNKNOWN_ZONE)
        assert len(spec.filter(pool)) == 2

    def test_not_inverts(self, pool):
        assert {str(c.id) for c in (~IsAlive()).filter(pool)} == {
            "concept_bbbb2222",
            "concept_cccc3333",
        }

    def test_specifications_nest_arbitrarily(self, pool):
        spec = (IsAlive() & ScoredAbove(50)) | (IsRevivable() & HasTheme("dívida"))
        assert {str(c.id) for c in spec.filter(pool)} == {
            "concept_aaaa1111",
            "concept_dddd4444",
            "concept_cccc3333",
        }

    def test_double_negation_is_identity(self, pool):
        assert {str(c.id) for c in (~~IsAlive()).filter(pool)} == {
            str(c.id) for c in IsAlive().filter(pool)
        }

    def test_is_satisfied_by_works_on_a_single_candidate(self, pool):
        assert IsAlive().is_satisfied_by(pool[0])
        assert not IsAlive().is_satisfied_by(pool[2])
