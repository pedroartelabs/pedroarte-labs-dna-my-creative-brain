"""End-to-end: the mandatory vertical slice.

    BOOT → AWAKEN → OBSERVE → QUESTION → GENERATE SEEDS → BUILD CONCEPTS
         → EVALUATE → TOURNAMENT → JUDGE → SAVE WINNER
         → CONSOLIDATE MEMORY → DREAM → SLEEP → RESUME

Entirely offline: FakeClock, SeededRandom, MockLLM. No network, no API key,
no real time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from creative_brain.composition import Brain, build_brain
from creative_brain.domain.entities.circadian import BiologicalPhase
from creative_brain.domain.events import EventName
from creative_brain.domain.policies.lifecycle import CreativeStage

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def cycle(tmp_path_factory) -> tuple[Brain, dict]:
    """Run exactly one complete creative cycle and hand back the brain plus outcome."""
    import shutil

    repo_root = Path(__file__).resolve().parents[2]
    root = tmp_path_factory.mktemp("e2e")
    for name in ("config", "prompts"):
        shutil.copytree(repo_root / name, root / name)
    shutil.copytree(repo_root / "memory" / "core_dna", root / "memory" / "core_dna")
    for name in ("memory/evolving_dna", "outputs", "logs", "input"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "input" / "manifesto.md").write_text(
        "A distopia mais forte não é inventada: é um procedimento existente aplicado "
        "corretamente até o fim.",
        encoding="utf-8",
    )

    brain = build_brain(root, mock=True, quiet=True, fake_clock=True, seed=2026)
    outcome = brain.runtime.run_single_cycle()
    return brain, outcome


class TestTheCycleCompletes:
    def test_it_walks_from_awakening_to_deep_sleep(self, cycle):
        _, outcome = cycle
        phases = outcome["phases"]
        assert phases[0] == str(BiologicalPhase.AWAKENING)
        assert phases[-1] == str(BiologicalPhase.DEEP_SLEEP)

    def test_it_visits_every_essential_phase(self, cycle):
        _, outcome = cycle
        phases = set(outcome["phases"])
        for required in (
            BiologicalPhase.AWAKENING,
            BiologicalPhase.OBSERVATION,
            BiologicalPhase.FOCUS,
            BiologicalPhase.CREATION,
            BiologicalPhase.REFLECTION,
            BiologicalPhase.CONSOLIDATION,
            BiologicalPhase.DREAMING,
            BiologicalPhase.DEEP_SLEEP,
        ):
            assert str(required) in phases

    def test_no_phase_runs_twice(self, cycle):
        _, outcome = cycle
        assert len(outcome["phases"]) == len(set(outcome["phases"]))


class TestItActuallyProduced:
    def test_it_observed_researched_and_questioned(self, cycle):
        _, outcome = cycle
        counts = outcome["counts"]
        assert counts["observations"] > 0
        assert counts["questions"] > 0
        assert counts["seeds"] > 0
        assert counts["concepts"] > 0

    def test_selection_pressure_was_real(self, cycle):
        """A tournament that eliminates nothing is not a tournament."""
        _, outcome = cycle
        assert outcome["counts"]["rejected"] > 0

    def test_every_generator_contributed(self, cycle):
        brain, _ = cycle
        mechanisms = {
            str(seed.origin.mechanism)
            for seed in brain.context.repositories.seeds.list_for_cycle(
                brain.runtime.state.cycle_id
            )
        }
        assert {"what_if", "collision", "inversion", "paradox", "unknown_zone"} <= mechanisms

    def test_ideas_were_spread_across_the_zones(self, cycle):
        brain, _ = cycle
        zones = {
            str(c.genome.creative_distance.zone)
            for c in brain.context.repositories.concepts.list_recent(limit=200)
        }
        assert len(zones) >= 2, f"all ideas landed in the same zone: {zones}"


class TestTheWinner:
    def test_a_winner_was_selected(self, cycle):
        _, outcome = cycle
        assert outcome["winner_title"], "the judge approved nothing"
        assert outcome["project_id"]

    def test_the_winner_reached_production_ready(self, cycle):
        brain, outcome = cycle
        concept = brain.context.repositories.concepts.get(outcome["winner_id"])
        assert concept is not None
        assert concept.stage is CreativeStage.PRODUCTION_READY

    def test_the_winner_carries_every_artifact(self, cycle):
        brain, outcome = cycle
        concept = brain.context.repositories.concepts.get(outcome["winner_id"])
        for key in ("premise", "pitch", "synopsis", "world_bible", "characters"):
            assert concept.artifacts.get(key, "").strip(), f"missing artifact: {key}"

    def test_the_winner_has_a_central_question(self, cycle):
        brain, outcome = cycle
        concept = brain.context.repositories.concepts.get(outcome["winner_id"])
        assert concept.central_question.strip()

    def test_the_winner_carries_a_complete_genome(self, cycle):
        brain, outcome = cycle
        genome = brain.context.repositories.concepts.get(outcome["winner_id"]).genome
        assert genome.origin.mechanism
        assert genome.themes
        assert 0 <= genome.creative_distance.value <= 100
        assert 0 <= genome.novelty_score.value <= 100

    def test_the_decision_is_explainable(self, cycle):
        """Article 14: persisted evidence, not a black box."""
        brain, outcome = cycle
        project = brain.context.repositories.projects.get(outcome["project_id"])
        assert project.decision_traces
        trace = project.decision_traces[0]
        assert trace.who and trace.what and trace.why


class TestArtifactsOnDisk:
    def test_the_cycle_directory_is_complete(self, cycle):
        brain, outcome = cycle
        root = Path(brain.context.output.cycle_root(outcome["cycle_id"]))
        for relative in (
            "observations/observations.json",
            "questions/questions.json",
            "seeds/seeds.json",
            "concepts/concepts.json",
            "concepts/leaderboard.md",
            "rejected/rejected.json",
            "tournament/tournament.json",
            "finalists/finalists.json",
            "learning/learning.json",
            "learning/dream.json",
            "runtime/runtime.json",
        ):
            assert (root / relative).exists(), f"missing artifact: {relative}"

    def test_the_winner_package_is_complete(self, cycle):
        brain, outcome = cycle
        root = Path(brain.context.output.cycle_root(outcome["cycle_id"]))
        for relative in (
            "winner/concept.md",
            "winner/premise.md",
            "winner/pitch.md",
            "winner/synopsis.md",
            "winner/world_bible.md",
            "winner/characters.md",
            "winner/evaluation.json",
            "winner/execution_manifest.json",
            "genome/creative_genome.yaml",
        ):
            path = root / relative
            assert path.exists(), f"missing artifact: {relative}"
            assert path.stat().st_size > 40, f"artifact is a stub: {relative}"

    def test_the_execution_manifest_is_valid_for_hand_off(self, cycle):
        brain, outcome = cycle
        root = Path(brain.context.output.cycle_root(outcome["cycle_id"]))
        manifest = json.loads(
            (root / "winner" / "execution_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["status"] == "PRODUCTION_READY"
        assert manifest["project_id"] == outcome["project_id"]
        assert manifest["recommended_engines"]
        assert manifest["artifacts"]
        assert manifest["creative_scores"]["total"] > 0

    def test_the_runtime_manifest_records_how_to_replay(self, cycle):
        brain, outcome = cycle
        root = Path(brain.context.output.cycle_root(outcome["cycle_id"]))
        runtime = json.loads((root / "runtime" / "runtime.json").read_text(encoding="utf-8"))
        assert runtime["random_seed"] == 2026
        assert runtime["flags"]
        assert runtime["metrics"]["counters"]
        assert runtime["dead_letters"] == 0


class TestEventsTellTheWholeStory:
    def test_the_narrative_events_were_all_published(self, cycle):
        brain, _ = cycle
        published = {e.name for e in brain.bus.history()}
        for required in (
            EventName.CYCLE_STARTED,
            EventName.CIRCADIAN_PHASE_CHANGED,
            EventName.OBSERVATION_CAPTURED,
            EventName.QUESTION_GENERATED,
            EventName.SEED_CREATED,
            EventName.CONCEPT_CREATED,
            EventName.CONCEPT_REJECTED,
            EventName.TOURNAMENT_STARTED,
            EventName.TOURNAMENT_FINISHED,
            EventName.IDEA_APPROVED,
            EventName.PROJECT_PRODUCTION_READY,
            EventName.MEMORY_CONSOLIDATED,
            EventName.DNA_UPDATED,
            EventName.DREAM_STARTED,
            EventName.DREAM_FINISHED,
            EventName.CYCLE_FINISHED,
        ):
            assert required in published, f"never published: {required}"

    def test_every_event_is_correlated_to_its_cycle(self, cycle):
        brain, outcome = cycle
        cycle_events = [e for e in brain.bus.history() if e.cycle_id]
        assert cycle_events
        assert all(e.cycle_id == outcome["cycle_id"] for e in cycle_events)

    def test_nothing_ended_up_in_the_dead_letter_queue(self, cycle):
        brain, _ = cycle
        assert brain.bus.dead_letters() == []


class TestLearningAndMemory:
    def test_memory_was_consolidated(self, cycle):
        brain, _ = cycle
        assert brain.context.repositories.memory.count() > 0

    def test_the_evolving_dna_advanced(self, cycle):
        brain, outcome = cycle
        assert outcome["dna_version"] >= 1
        assert brain.context.repositories.dna.load_evolving().version >= 1

    def test_the_corpus_was_ingested_and_indexed(self, cycle):
        brain, _ = cycle
        assert brain.context.vectors.size() > 0

    def test_the_creative_graph_recorded_lineage(self, cycle):
        brain, _ = cycle
        graph = brain.context.graph.export()
        assert graph["nodes"]
        assert graph["edges"]


class TestResilienceAndReplay:
    def test_the_runtime_reports_itself_healthy(self, cycle):
        brain, _ = cycle
        assert brain.runtime.evaluate_health().healthy

    def test_no_agent_is_broken(self, cycle):
        brain, _ = cycle
        assert brain.context.society.unhealthy() == []

    def test_it_resumes_instead_of_starting_from_zero(self, cycle):
        """A restarted brain must pick the cycle counter back up."""
        brain, _ = cycle
        root = Path(brain.context.output.cycle_root("x")).parents[2]

        resumed = build_brain(root, mock=True, quiet=True, fake_clock=True, seed=2026)
        resumed.runtime.bootstrap()

        assert resumed.runtime.cycles_completed == 1
        assert resumed.runtime.state.cycle_number == brain.runtime.state.cycle_number
        assert resumed.runtime.state.cycle_id == brain.runtime.state.cycle_id

    def test_a_second_cycle_builds_on_the_first(self, cycle):
        brain, _ = cycle
        root = Path(brain.context.output.cycle_root("x")).parents[2]

        second = build_brain(root, mock=True, quiet=True, fake_clock=True, seed=7)
        outcome = second.runtime.run_single_cycle()

        assert second.runtime.state.cycle_number == 2
        assert outcome["cycle_id"] != brain.runtime.state.cycle_id
        # The second cycle sees the first one's memory.
        assert second.context.repositories.memory.count() > 0
        assert second.context.repositories.dna.load_evolving().version >= 2

    def test_the_budget_was_tracked(self, cycle):
        brain, _ = cycle
        assert brain.budget.calls > 0
        assert brain.budget.cost_usd > 0
        assert brain.budget.calls < brain.budget.max_calls_per_cycle
