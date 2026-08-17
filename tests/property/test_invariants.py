"""Property-based tests for the invariants the whole engine leans on.

If any of these can be broken, every score, every ranking and every circadian
decision downstream becomes untrustworthy.
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from creative_brain.domain.policies.exploration import ExplorationPolicy
from creative_brain.domain.policies.scoring import DEFAULT_WEIGHTS, ScoringPolicy
from creative_brain.domain.services.evaluation import DiversityService, NoveltyService
from creative_brain.domain.services.similarity import jaccard, similarity
from creative_brain.domain.value_objects.creative_distance import CreativeDistance, CreativeZone
from creative_brain.domain.value_objects.dna import EvolvingDna
from creative_brain.domain.value_objects.energy import EnergyKind, EnergyLevel, EnergyProfile
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard, ScoreCriterion

reals = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)
in_range = st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)

#: Arbitrary text, including text with no content words at all.
texts = st.text(min_size=0, max_size=200)

#: Text guaranteed to survive tokenization. Built from real vocabulary rather
#: than filtered with assume(), which would discard most generated inputs.
content_words = st.sampled_from(
    [
        "cartorio",
        "memoria",
        "heranca",
        "divida",
        "condominio",
        "protocolo",
        "familia",
        "registro",
        "certidao",
        "consignado",
    ]
)
content_texts = st.lists(content_words, min_size=1, max_size=10).map(" ".join)


class TestScoreInvariants:
    @given(reals)
    def test_a_clamped_score_is_always_in_range(self, value: float):
        assert 0.0 <= CreativeScore.clamped(value).value <= 100.0

    @given(in_range, in_range, st.floats(min_value=0, max_value=1))
    def test_blending_never_leaves_the_range(self, a: float, b: float, weight: float):
        assert 0.0 <= CreativeScore(a).blend(CreativeScore(b), weight).value <= 100.0

    @given(in_range, in_range)
    def test_blending_stays_between_the_endpoints(self, a: float, b: float):
        # Scores round to 4 decimals by design, so the bound is checked within
        # half of that quantum rather than exactly.
        tolerance = 5e-5
        blended = CreativeScore(a).blend(CreativeScore(b), 0.5).value
        assert min(a, b) - tolerance <= blended <= max(a, b) + tolerance

    @given(st.dictionaries(st.sampled_from([c.value for c in ScoreCriterion]), in_range))
    def test_a_weighted_total_is_always_in_range(self, raw: dict[str, float]):
        board = ScoreBoard.from_mapping(raw)
        assert 0.0 <= board.weighted_total(DEFAULT_WEIGHTS).value <= 100.0

    @given(st.dictionaries(st.sampled_from([c.value for c in ScoreCriterion]), in_range))
    def test_merging_a_board_with_itself_is_identity(self, raw: dict[str, float]):
        board = ScoreBoard.from_mapping(raw)
        assert board.merge(board).as_dict() == board.as_dict()

    @given(st.dictionaries(st.sampled_from([c.value for c in ScoreCriterion]), in_range))
    def test_a_perfect_board_scores_one_hundred(self, raw: dict[str, float]):
        perfect = ScoreBoard.from_mapping({c.value: 100.0 for c in ScoreCriterion})
        assert perfect.weighted_total(DEFAULT_WEIGHTS).value == 100.0


class TestDistanceInvariants:
    @given(reals)
    def test_a_clamped_distance_is_always_in_range(self, value: float):
        assert 0.0 <= CreativeDistance.clamped(value).value <= 100.0

    @given(in_range)
    def test_every_distance_maps_to_exactly_one_zone(self, value: float):
        assert CreativeDistance(value).zone in set(CreativeZone)

    @given(in_range)
    def test_zones_are_monotonic_in_distance(self, value: float):
        order = {
            CreativeZone.COMFORT_ZONE: 0,
            CreativeZone.EDGE_ZONE: 1,
            CreativeZone.UNKNOWN_ZONE: 2,
        }
        lower = CreativeDistance(max(0.0, value - 1)).zone
        assert order[lower] <= order[CreativeDistance(value).zone]


class TestEnergyInvariants:
    @given(reals)
    def test_a_clamped_gauge_is_always_in_range(self, value: float):
        assert 0.0 <= EnergyLevel.clamped(value).value <= 100.0

    @given(in_range, st.floats(min_value=0, max_value=1000, allow_nan=False))
    def test_spending_never_goes_negative(self, start: float, amount: float):
        assert EnergyLevel(start).spend(amount).value >= 0.0

    @given(in_range, st.floats(min_value=0, max_value=1000, allow_nan=False))
    def test_restoring_never_exceeds_full(self, start: float, amount: float):
        assert EnergyLevel(start).restore(amount).value <= 100.0

    @given(st.lists(st.sampled_from(list(EnergyKind)), max_size=30), in_range)
    def test_a_profile_stays_valid_through_any_sequence(
        self, kinds: list[EnergyKind], amount: float
    ):
        profile = EnergyProfile.rested()
        for kind in kinds:
            profile = profile.spend(kind, amount).restore(kind, amount / 2)
        assert all(0.0 <= v <= 100.0 for v in profile.as_dict().values())

    @given(in_range, in_range)
    def test_sleep_never_makes_things_worse(self, creative: float, pressure: float):
        profile = EnergyProfile(
            creative=EnergyLevel(creative), memory_pressure=EnergyLevel(pressure)
        )
        rested = profile.restored_by_sleep()
        assert rested.creative.value >= profile.creative.value
        assert rested.memory_pressure.value <= profile.memory_pressure.value


class TestSimilarityInvariants:
    @given(content_texts)
    def test_a_text_is_maximally_similar_to_itself(self, text: str):
        assert similarity(text, text) == 1.0

    @given(texts)
    def test_text_without_content_words_is_never_similar(self, text: str):
        from creative_brain.domain.services.similarity import token_set

        assume(not token_set(text))
        assert similarity(text, "cartorio memoria heranca") == 0.0

    @given(texts, texts)
    def test_similarity_is_bounded(self, a: str, b: str):
        assert 0.0 <= similarity(a, b) <= 1.0

    @given(texts, texts)
    def test_similarity_is_symmetric(self, a: str, b: str):
        assert similarity(a, b) == similarity(b, a)

    @given(texts, texts)
    def test_jaccard_is_bounded_and_symmetric(self, a: str, b: str):
        assert 0.0 <= jaccard(a, b) <= 1.0
        assert jaccard(a, b) == jaccard(b, a)

    @given(st.lists(texts, min_size=1, max_size=8))
    def test_diversity_is_always_a_percentage(self, batch: list[str]):
        assert 0.0 <= DiversityService().score(batch) <= 100.0

    @given(st.lists(texts, min_size=1, max_size=8))
    def test_duplicate_rate_is_always_a_ratio(self, batch: list[str]):
        assert 0.0 <= NoveltyService().duplicate_rate(batch) <= 1.0

    @given(texts, st.dictionaries(st.text(min_size=1, max_size=6), texts, max_size=6))
    def test_novelty_is_always_a_valid_score(self, text: str, corpus: dict[str, str]):
        assessment = NoveltyService().assess(text, corpus)
        assert 0.0 <= assessment.novelty.value <= 100.0


class TestExplorationInvariants:
    @given(st.integers(min_value=0, max_value=5000))
    def test_allocation_conserves_every_slot(self, total: int):
        assert sum(ExplorationPolicy().allocate(total).values()) == total

    @given(st.integers(min_value=0, max_value=500))
    def test_allocation_is_never_negative(self, total: int):
        assert all(v >= 0 for v in ExplorationPolicy().allocate(total).values())

    @given(
        st.floats(min_value=0.01, max_value=0.98),
        st.integers(min_value=1, max_value=200),
    )
    def test_any_valid_split_conserves_slots(self, comfort: float, total: int):
        remaining = 1.0 - comfort
        policy = ExplorationPolicy(
            comfort=comfort, edge=remaining * 0.7, unknown=remaining * 0.3
        )
        assert sum(policy.allocate(total).values()) == total


class TestDnaInvariants:
    @given(st.lists(st.text(min_size=1, max_size=20), max_size=25))
    @settings(max_examples=40)
    def test_learning_only_ever_increments_the_version(self, entries: list[str]):
        dna = EvolvingDna()
        for entry in entries:
            before = dna.version
            dna = dna.learn(discoveries=(entry,))
            assert dna.version == before + 1

    @given(st.lists(st.text(min_size=1, max_size=12), max_size=200))
    @settings(max_examples=25)
    def test_buckets_never_exceed_their_cap(self, entries: list[str]):
        dna = EvolvingDna().learn(discoveries=tuple(entries))
        assert len(dna.discoveries) <= EvolvingDna.MAX_ENTRIES_PER_BUCKET

    @given(st.lists(st.text(min_size=1, max_size=12), max_size=30))
    def test_learning_never_produces_duplicates(self, entries: list[str]):
        dna = EvolvingDna().learn(discoveries=tuple(entries))
        lowered = [d.strip().lower() for d in dna.discoveries]
        assert len(lowered) == len(set(lowered))


class TestScoringPolicyInvariants:
    @given(
        st.dictionaries(
            st.sampled_from([c.value for c in ScoreCriterion if c != ScoreCriterion.COMMERCIAL_POTENTIAL]),
            st.floats(min_value=0.01, max_value=1.0),
            min_size=1,
        )
    )
    def test_any_non_commercial_weighting_is_accepted(self, weights: dict[str, float]):
        policy = ScoringPolicy.from_mapping(weights)
        assert sum(policy.weights.values()) > 0
