"""Scoring, selection pressure and the creative tournament."""

from __future__ import annotations

import pytest

from creative_brain.domain.entities.agent_opinion import AgentOpinion, Verdict
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.tournament import (
    CreativeTournament,
    FunnelStep,
    TournamentFunnel,
)
from creative_brain.domain.exceptions import (
    EmptyTournamentError,
    InvalidCreativeScore,
    TournamentFailure,
)
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.policies.scoring import DEFAULT_WEIGHTS, ScoringPolicy
from creative_brain.domain.services.evaluation import DiversityService
from creative_brain.domain.services.tournament_service import TournamentService
from creative_brain.domain.value_objects.creative_distance import CreativeDistance
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId, TournamentId
from creative_brain.domain.value_objects.scores import CreativeScore, ScoreBoard, ScoreCriterion

ORIGIN = GenomeOrigin(mechanism=OriginMechanism.COLLISION)


def candidate(token: str, title: str, logline: str, **scores: float) -> CreativeConcept:
    concept = CreativeConcept.germinate(
        concept_id=ConceptId.from_token(token),
        title=title,
        logline=logline,
        origin=ORIGIN,
        at="2026-01-01T06:00:00Z",
        cycle_id="cycle_test0001",
    )
    concept.pull_events()
    concept.scoreboard = ScoreBoard.from_mapping(
        {c.value: scores.get(c.value, 60.0) for c in ScoreCriterion}
    )
    concept.apply_evaluation(distance=CreativeDistance(55))
    concept.apply_total(ScoringPolicy().total_for(concept), at="now")
    return concept


class TestScoringPolicy:
    def test_default_weights_are_the_documented_ones(self):
        assert DEFAULT_WEIGHTS[ScoreCriterion.ORIGINALITY] == 0.20
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_market_can_never_dominate(self):
        """Article 13: MarketScore must never decide artistic quality alone."""
        with pytest.raises(InvalidCreativeScore, match="commercial"):
            ScoringPolicy(
                weights={
                    ScoreCriterion.COMMERCIAL_POTENTIAL: 0.9,
                    ScoreCriterion.ORIGINALITY: 0.1,
                }
            )

    def test_weights_must_be_positive(self):
        with pytest.raises(InvalidCreativeScore):
            ScoringPolicy(weights={ScoreCriterion.DEPTH: 0.0})

    def test_a_blocking_veto_caps_the_total(self):
        concept = candidate("aaaa1111", "Alta", "muito boa", **dict.fromkeys(
            [c.value for c in ScoreCriterion], 95.0
        ))
        uncapped = ScoringPolicy().total_for(concept).value
        concept.add_opinion(
            AgentOpinion(
                agent="ANTI_CLICHE_AGENT",
                verdict=Verdict.REJECT,
                rationale="derivativo",
                created_at="now",
                confidence=90.0,
            )
        )
        capped = ScoringPolicy().total_for(concept).value
        assert uncapped > capped == 45.0

    def test_low_originality_disqualifies_regardless_of_score(self):
        concept = candidate("bbbb2222", "Cópia", "quase igual", originality=10.0)
        reason = ScoringPolicy().disqualifies(concept)
        assert reason is not None and "originality" in reason

    def test_a_near_copy_is_disqualified(self):
        concept = candidate("cccc3333", "Eco", "eco de outra obra")
        concept.apply_evaluation(distance=CreativeDistance(4))
        assert "near-copy" in (ScoringPolicy().disqualifies(concept) or "")

    def test_configuration_overrides_the_defaults(self):
        policy = ScoringPolicy.from_mapping({"originality": 1.0, "unknown_criterion": 5.0})
        assert list(policy.weights) == [ScoreCriterion.ORIGINALITY]


class TestFunnel:
    def test_a_funnel_must_narrow(self):
        with pytest.raises(TournamentFailure):
            TournamentFunnel.from_pairs([("CONCEPT", 3), ("PREMISE", 10)])

    def test_a_round_must_keep_at_least_one(self):
        with pytest.raises(TournamentFailure):
            FunnelStep(CreativeStage.CONCEPT, 0)

    def test_an_empty_funnel_is_refused(self):
        with pytest.raises(TournamentFailure):
            TournamentFunnel(())

    def test_the_last_round_defines_the_finalists(self):
        funnel = TournamentFunnel.from_pairs([("CONCEPT", 10), ("FINALIST", 3)])
        assert funnel.winners == 3


class TestSelection:
    def test_the_strongest_survive(self):
        service = TournamentService(scoring=ScoringPolicy())
        pool = [
            candidate("aaaa1111", "Cartório das Memórias", "herança registrada", depth=95),
            candidate("bbbb2222", "Fila Vitalícia", "espera como patrimônio", depth=20),
            candidate("cccc3333", "Boleto Hereditário", "dívida transferida", depth=55),
        ]
        outcome = service.select(pool, keep=2)
        assert len(outcome.survivors) == 2
        assert "Cartório das Memórias" in [c.title for c in outcome.survivors]

    def test_every_elimination_carries_a_reason(self):
        service = TournamentService(scoring=ScoringPolicy())
        pool = [
            candidate("aaaa1111", "Primeira", "uma ideia sobre cartórios e memória"),
            candidate("bbbb2222", "Segunda", "outra coisa completamente diferente sobre filas"),
        ]
        outcome = service.select(pool, keep=1)
        for loser in outcome.eliminated:
            assert outcome.reasons[str(loser.id)]

    def test_redundant_survivors_are_cut(self):
        """Article 11: disguised conceptual repetition is not allowed."""
        service = TournamentService(scoring=ScoringPolicy())
        text = "cartório registra memória como patrimônio hereditário da família"
        pool = [
            candidate("aaaa1111", "Registro de Memória", text),
            candidate("bbbb2222", "Memória Registrada", text),
            candidate("cccc3333", "Fila do Banco", "uma espera que vira profissão hereditária"),
        ]
        outcome = service.select(pool, keep=2)
        titles = [c.title for c in outcome.survivors]
        assert not ({"Registro de Memória", "Memória Registrada"} <= set(titles))

    def test_a_round_never_comes_back_empty(self):
        """Even when everything is disqualified, the cycle must be able to finish."""
        service = TournamentService(scoring=ScoringPolicy())
        pool = [candidate("aaaa1111", "Fraca", "derivativa", originality=5.0)]
        outcome = service.select(pool, keep=1)
        assert len(outcome.survivors) == 1
        assert "fallback" in outcome.reasons[str(outcome.survivors[0].id)]

    def test_selecting_from_nothing_is_an_error(self):
        with pytest.raises(EmptyTournamentError):
            TournamentService(scoring=ScoringPolicy()).select([], keep=1)

    def test_the_funnel_narrows_monotonically(self):
        service = TournamentService(scoring=ScoringPolicy())
        pool = [
            candidate(f"aaaa{i:04d}", f"Ideia {i}", f"premissa distinta número {i} sobre {w}")
            for i, w in enumerate(
                ["cartório", "banco", "condomínio", "INSS", "seguro", "sindicato"]
            )
        ]
        funnel = TournamentFunnel.from_pairs([("CONCEPT", 4), ("PREMISE", 2)])
        outcomes = service.run_funnel(pool, funnel)
        assert len(outcomes[0].survivors) <= 4
        assert len(outcomes[1].survivors) <= 2


class TestTournamentAggregate:
    def test_a_tournament_needs_entrants(self):
        with pytest.raises(EmptyTournamentError):
            CreativeTournament.start(
                tournament_id=TournamentId.from_token("aaaa1111"),
                cycle_id="cycle_test0001",
                funnel=TournamentFunnel.from_pairs([("CONCEPT", 1)]),
                entrants=(),
                at="now",
            )

    def test_finishing_is_idempotent(self):
        """Re-processing a tournament must not corrupt the result."""
        tournament = self._started()
        tournament.finish(winner_id="concept_aaaa1111", at="now")
        tournament.finish(winner_id="concept_aaaa1111", at="later")
        assert tournament.winner_id == "concept_aaaa1111"
        assert tournament.finished_at == "now"

    def test_finishing_with_a_different_winner_is_refused(self):
        tournament = self._started()
        tournament.finish(winner_id="concept_aaaa1111", at="now")
        with pytest.raises(TournamentFailure):
            tournament.finish(winner_id="concept_bbbb2222", at="now")

    def test_rounds_record_who_fell(self):
        tournament = self._started()
        tournament.record_round(
            stage=CreativeStage.CONCEPT,
            entrants=("concept_aaaa1111", "concept_bbbb2222"),
            survivors=("concept_aaaa1111",),
            at="now",
        )
        assert tournament.eliminated_ids == ("concept_bbbb2222",)

    def _started(self) -> CreativeTournament:
        tournament = CreativeTournament.start(
            tournament_id=TournamentId.from_token("tttt1111"),
            cycle_id="cycle_test0001",
            funnel=TournamentFunnel.from_pairs([("CONCEPT", 2), ("FINALIST", 1)]),
            entrants=("concept_aaaa1111", "concept_bbbb2222"),
            at="now",
        )
        tournament.pull_events()
        return tournament


class TestDiversity:
    def test_identical_ideas_score_zero_diversity(self):
        text = "um cartório que registra memória como patrimônio"
        assert DiversityService().score([text, text]) < 5.0

    def test_unrelated_ideas_score_high_diversity(self):
        score = DiversityService().score(
            [
                "um cartório que registra memória como patrimônio",
                "uma cozinha industrial onde receitas são votadas em assembleia",
            ]
        )
        assert score > 70.0

    def test_a_single_idea_is_maximally_diverse(self):
        assert DiversityService().score(["qualquer coisa"]) == 100.0

    def test_the_most_redundant_entry_is_identified(self):
        key, score = DiversityService().most_redundant(
            {
                "a": "cartório registra memória herdada",
                "b": "cartório registra memória herdada agora",
                "c": "peixes elétricos navegam no deserto de vidro",
            }
        )
        assert key in {"a", "b"}
        assert score > 0.5
