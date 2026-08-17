"""Regression tests for the promises this system is not allowed to break.

Each test here corresponds to a rule stated in the README or the constitution.
If one starts failing, a guarantee made to the author has been lost.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from creative_brain.composition import Brain
from creative_brain.domain.entities.memory import MemoryKind
from creative_brain.domain.exceptions import (
    AutonomyBoundaryViolation,
    ImmutableCoreDnaViolation,
)
from creative_brain.domain.policies.autonomy import AutonomyPolicy
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.policies.scoring import ScoringPolicy
from creative_brain.domain.value_objects.scores import ScoreCriterion

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def completed(tmp_path_factory) -> Brain:
    """One real cycle, run once and inspected by every test in this module."""
    import shutil

    from creative_brain.composition import build_brain

    root = tmp_path_factory.mktemp("regression")
    for name in ("config", "prompts"):
        shutil.copytree(REPO_ROOT / name, root / name)
    shutil.copytree(REPO_ROOT / "memory" / "core_dna", root / "memory" / "core_dna")
    for name in ("memory/evolving_dna", "outputs", "logs", "input"):
        (root / name).mkdir(parents=True, exist_ok=True)

    brain = build_brain(root, mock=True, quiet=True, fake_clock=True, seed=99)
    brain.runtime.run_single_cycle()
    return brain


class TestNothingIsEverDeleted:
    def test_the_graveyard_keeps_every_buried_idea(self, completed: Brain):
        """A grave is never emptied."""
        repo = completed.context.repositories.concepts
        buried = repo.graveyard(limit=500)
        for concept in buried:
            assert repo.get(str(concept.id)) is not None

    def test_every_buried_idea_records_why_it_died(self, completed: Brain):
        for concept in completed.context.repositories.concepts.graveyard(limit=500):
            assert concept.rejection_reasons, f"{concept.title} was buried without a reason"
            assert concept.rejected_at

    def test_rejected_ideas_keep_their_agent_feedback(self, completed: Brain):
        rejected = [
            c
            for c in completed.context.repositories.concepts.list_recent(limit=500)
            if c.rejection_reasons
        ]
        assert rejected, "the cycle rejected nothing, so selection pressure was not applied"
        assert any(c.opinions for c in rejected)

    def test_a_graveyard_entry_carries_mutation_potential(self, completed: Brain):
        for concept in completed.context.repositories.concepts.graveyard(limit=500):
            assert 0.0 <= concept.mutation_potential <= 100.0


class TestCoreDnaIsProtected:
    def test_the_core_dna_file_is_untouched_by_a_cycle(self, completed: Brain):
        original = (REPO_ROOT / "memory" / "core_dna" / "core_dna.json").read_bytes()
        used = (
            Path(completed.context.output.cycle_root("x")).parents[2]
            / "memory"
            / "core_dna"
            / "core_dna.json"
        )
        assert used.read_bytes() == original

    def test_the_engine_cannot_mutate_core_dna(self, completed: Brain):
        core = completed.context.repositories.dna.load_core()
        with pytest.raises(ImmutableCoreDnaViolation):
            core.mutate(identity="hacked")

    def test_the_dna_repository_exposes_no_core_writer(self, completed: Brain):
        assert not hasattr(completed.context.repositories.dna, "save_core")

    def test_only_evolving_dna_changed(self, completed: Brain):
        assert completed.context.repositories.dna.load_evolving().version >= 1


class TestAutonomyBoundary:
    @pytest.mark.parametrize(
        "action",
        [
            "publish_externally",
            "change_repository_visibility",
            "push_to_remote",
            "manage_credentials",
            "modify_source_code",
            "modify_core_dna",
            "delete_memory",
            "spend_money",
        ],
    )
    def test_infrastructure_always_needs_a_human(self, action: str):
        with pytest.raises(AutonomyBoundaryViolation):
            AutonomyPolicy().assert_not_restricted(action)

    def test_the_creative_loop_never_waits_for_approval(self, completed: Brain):
        """There is no WAIT_FOR_HUMAN_APPROVAL step anywhere in the runtime."""
        source = (REPO_ROOT / "src" / "creative_brain").rglob("*.py")
        offenders = [
            path.name
            for path in source
            if "WAIT_FOR_HUMAN_APPROVAL" in path.read_text(encoding="utf-8")
        ]
        assert not offenders


class TestConstitutionIsEnforced:
    def test_market_score_can_never_dominate(self):
        """Article 13: quality must beat quantity, and never be bought."""
        from creative_brain.domain.exceptions import InvalidCreativeScore

        with pytest.raises(InvalidCreativeScore):
            ScoringPolicy(
                weights={
                    ScoreCriterion.COMMERCIAL_POTENTIAL: 0.8,
                    ScoreCriterion.DEPTH: 0.2,
                }
            )

    def test_an_approved_project_always_has_a_central_question(self, completed: Brain):
        """Article 9."""
        for project in completed.context.repositories.projects.list_all(limit=50):
            assert project.central_question.strip()

    def test_an_approved_project_always_has_evidence(self, completed: Brain):
        """Article 14: every relevant decision is explainable by artifacts."""
        for project in completed.context.repositories.projects.list_all(limit=50):
            assert project.decision_traces
            assert project.artifacts

    def test_weights_live_in_configuration_not_in_code(self):
        """Article: never hide the weights in the source."""
        import yaml

        raw = yaml.safe_load((REPO_ROOT / "config" / "scoring.yaml").read_text(encoding="utf-8"))
        assert set(raw["weights"]) == {c.value for c in ScoreCriterion}


class TestMemoryDiscipline:
    def test_a_raw_event_is_never_stored_as_a_principle(self, completed: Brain):
        repo = completed.context.repositories.memory
        for record in repo.list_by_kind(MemoryKind.EPISODIC, limit=500):
            assert not record.is_principle

    def test_principles_are_kept_separately(self, completed: Brain):
        repo = completed.context.repositories.memory
        for record in repo.list_by_kind(MemoryKind.SEMANTIC, limit=500):
            assert record.is_principle


class TestLineageIsPreserved:
    def test_mutations_always_know_their_parent(self, completed: Brain):
        mutated = [
            c
            for c in completed.context.repositories.concepts.list_recent(limit=500)
            if any(link.relation.value == "mutated_from" for link in c.lineage.links)
        ]
        for concept in mutated:
            assert concept.lineage.ancestors

    def test_resurrections_point_back_at_the_grave(self, completed: Brain):
        revived = [
            c
            for c in completed.context.repositories.concepts.list_recent(limit=500)
            if any(link.relation.value == "resurrected_from" for link in c.lineage.links)
        ]
        repo = completed.context.repositories.concepts
        for concept in revived:
            source_id = next(
                link.ancestor_id
                for link in concept.lineage.links
                if link.relation.value == "resurrected_from"
            )
            source = repo.get(source_id)
            assert source is not None
            assert source.stage is CreativeStage.GRAVEYARD, "the original must stay buried"
