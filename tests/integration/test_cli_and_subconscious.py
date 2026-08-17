"""The CLI adapter and the subconscious use cases (mutation, dream, resurrection)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from creative_brain.application.use_cases.subconscious import (
    MutateRejectedConcepts,
    StartDreamCycle,
)
from creative_brain.cli.main import build_parser, main
from creative_brain.composition import Brain
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.events import EventName
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId


def dead_concept(brain: Brain, token: str, *, potential: float = 90.0) -> CreativeConcept:
    """A rejected concept sitting in the mutation pool."""
    concept = CreativeConcept.germinate(
        concept_id=ConceptId(f"concept_{token}"),
        title=f"Ideia {token}",
        logline="um cartório passa a registrar memória como herança",
        origin=GenomeOrigin(mechanism=OriginMechanism.COLLISION),
        at=brain.context.now(),
        cycle_id="cycle_test0001",
        themes=("memória",),
    )
    concept.advance_to(CreativeStage.CONCEPT, at=brain.context.now())
    concept.attach("premise", "a regra é aplicada corretamente e por isso destrói")
    concept.reject(("sem consequência",), at=brain.context.now())
    concept.send_to_mutation_pool(at=brain.context.now())
    concept.mutation_potential = potential
    concept.pull_events()
    brain.context.repositories.concepts.save(concept)
    return concept


class TestMutationEngine:
    def test_dead_ideas_get_a_structurally_different_second_life(self, brain: Brain):
        parent = dead_concept(brain, "aaaa1111")
        mutated = MutateRejectedConcepts(brain.context).execute(cycle_id="cycle_test0001")

        assert mutated, "the mutation engine produced nothing"
        child = mutated[0]
        assert child.genome.origin.mechanism is OriginMechanism.MUTATION
        assert child.lineage.has_ancestor(str(parent.id))
        assert child.stage is CreativeStage.CONCEPT

    def test_the_parent_is_buried_not_deleted(self, brain: Brain):
        parent = dead_concept(brain, "bbbb2222")
        MutateRejectedConcepts(brain.context).execute(cycle_id="cycle_test0001")

        stored = brain.context.repositories.concepts.get(str(parent.id))
        assert stored is not None
        assert stored.stage is CreativeStage.GRAVEYARD
        assert stored.rejection_reasons

    def test_weak_ideas_are_left_alone(self, brain: Brain):
        dead_concept(brain, "cccc3333", potential=5.0)
        assert MutateRejectedConcepts(brain.context).execute(cycle_id="cycle_test0001") == []

    def test_the_feature_flag_disables_it(self, brain: Brain):
        from dataclasses import replace

        dead_concept(brain, "dddd4444")
        brain.context.flags = replace(brain.context.flags, mutation_enabled=False)
        brain.context.policies.mutation = replace(
            brain.context.policies.mutation, enabled=False
        )
        assert MutateRejectedConcepts(brain.context).execute(cycle_id="cycle_test0001") == []

    def test_mutation_emits_its_event(self, brain: Brain):
        dead_concept(brain, "eeee5555")
        MutateRejectedConcepts(brain.context).execute(cycle_id="cycle_test0001")
        assert EventName.CONCEPT_MUTATED in {e.name for e in brain.bus.history()}

    def test_the_cycle_cap_is_respected(self, brain: Brain):
        for index in range(8):
            dead_concept(brain, f"ffff{index:04d}")
        mutated = MutateRejectedConcepts(brain.context).execute(cycle_id="cycle_test0001")
        assert len(mutated) <= brain.context.targets.mutations


class TestDreamMode:
    def test_a_dream_produces_fragments_and_harvests_seeds(self, brain: Brain):
        dream = StartDreamCycle(brain.context).execute(cycle_id="cycle_test0001")

        assert dream.fragments
        assert dream.harvested_seed_ids
        assert dream.finished_at
        assert 0 <= dream.strangeness <= 100

    def test_harvested_fragments_become_real_seeds(self, brain: Brain):
        dream = StartDreamCycle(brain.context).execute(cycle_id="cycle_test0001")
        seeds = brain.context.repositories.seeds.list_for_cycle("cycle_test0001")
        dreamt = [s for s in seeds if s.origin.mechanism is OriginMechanism.DREAM]

        assert len(dreamt) == len(dream.harvested_seed_ids)
        assert all(s.origin.dream == str(dream.id) for s in dreamt)

    def test_it_emits_start_and_finish(self, brain: Brain):
        StartDreamCycle(brain.context).execute(cycle_id="cycle_test0001")
        published = {e.name for e in brain.bus.history()}
        assert EventName.DREAM_STARTED in published
        assert EventName.DREAM_FINISHED in published

    def test_the_dream_is_persisted(self, brain: Brain):
        dream = StartDreamCycle(brain.context).execute(cycle_id="cycle_test0001")
        assert [d.id.value for d in brain.context.repositories.dreams.recent()] == [
            dream.id.value
        ]

    def test_resurrection_copies_and_leaves_the_grave_intact(self, brain: Brain):
        """Dream Mode may revive a buried idea — into a new lineage, never in place."""
        buried = []
        for index in range(6):
            concept = dead_concept(brain, f"9999{index:04d}")
            concept.entomb(at=brain.context.now())
            concept.mutation_potential = 95.0
            concept.pull_events()
            brain.context.repositories.concepts.save(concept)
            buried.append(concept)

        dream = StartDreamCycle(brain.context).execute(cycle_id="cycle_test0002")

        for concept in buried:
            stored = brain.context.repositories.concepts.get(str(concept.id))
            assert stored.stage is CreativeStage.GRAVEYARD

        for revived_id in dream.resurrected_ids:
            revived = brain.context.repositories.concepts.get(revived_id)
            assert revived.stage is CreativeStage.MUTATION_POOL
            assert revived.lineage.ancestors


class TestCliSurface:
    def test_the_parser_exposes_every_documented_command(self):
        parser = build_parser()
        for argv in (
            ["start"],
            ["demo"],
            ["status"],
            ["stop"],
            ["cycle", "run"],
            ["memory", "inspect"],
            ["graveyard", "inspect"],
            ["tournament", "inspect"],
            ["agents", "list"],
            ["clock", "status"],
        ):
            assert parser.parse_args(argv) is not None

    def test_a_missing_command_is_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_agents_list_reports_the_whole_society(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--mock", "--json", "agents", "list"]) == 0
        catalogue = json.loads(capsys.readouterr().out)
        assert len(catalogue) >= 30
        ids = {agent["id"] for agent in catalogue}
        assert {"CREATIVE_JUDGE_AGENT", "THE_UNKNOWN_AGENT", "BIOLOGICAL_CLOCK_AGENT"} <= ids

    def test_the_clock_agent_is_a_policy_not_an_llm_agent(self, project_root: Path, capsys):
        main(["--root", str(project_root), "--mock", "--json", "agents", "list"])
        catalogue = json.loads(capsys.readouterr().out)
        clock = next(a for a in catalogue if a["id"] == "BIOLOGICAL_CLOCK_AGENT")
        assert clock["live"] is False, "the clock must not be an LLM-backed agent"
        assert "schedule" in clock["decision_rights"]

    def test_clock_status_renders(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--mock", "--json", "clock", "status"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert "energy" in report and "budgets" in report

    def test_status_on_a_fresh_brain_is_idle(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--mock", "--json", "status"]) == 0
        status = json.loads(capsys.readouterr().out)
        assert status["running"] is False
        assert status["cycle_number"] == 0

    def test_an_empty_graveyard_renders_cleanly(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--mock", "graveyard", "inspect"]) == 0
        assert "graveyard is empty" in capsys.readouterr().out

    def test_inspecting_a_tournament_before_any_exists(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--mock", "tournament", "inspect"]) == 0
        assert "no tournaments" in capsys.readouterr().out

    def test_a_single_cycle_runs_and_reports(self, project_root: Path, capsys):
        exit_code = main(
            ["--root", str(project_root), "--mock", "--quiet", "--json", "start", "--single-cycle"]
        )
        assert exit_code == 0
        outcome = json.loads(capsys.readouterr().out)
        assert outcome["cycle_id"]
        assert outcome["counts"]["concepts"] > 0

    def test_status_after_a_cycle_reflects_the_work(self, project_root: Path, capsys):
        main(["--root", str(project_root), "--mock", "--quiet", "start", "--single-cycle"])
        capsys.readouterr()

        main(["--root", str(project_root), "--mock", "--json", "status"])
        status = json.loads(capsys.readouterr().out)
        assert status["cycle_number"] == 1
        assert status["counts"]["concepts"] > 0

    def test_memory_and_graveyard_inspect_after_a_cycle(self, project_root: Path, capsys):
        main(["--root", str(project_root), "--mock", "--quiet", "start", "--single-cycle"])
        capsys.readouterr()

        main(["--root", str(project_root), "--mock", "--json", "memory", "inspect", "--limit", "5"])
        records = json.loads(capsys.readouterr().out)
        assert records

        main(["--root", str(project_root), "--mock", "--json", "graveyard", "inspect"])
        assert isinstance(json.loads(capsys.readouterr().out), list)

    def test_tournament_inspect_after_a_cycle(self, project_root: Path, capsys):
        main(["--root", str(project_root), "--mock", "--quiet", "start", "--single-cycle"])
        capsys.readouterr()

        main(["--root", str(project_root), "--mock", "tournament", "inspect"])
        rendered = capsys.readouterr().out
        assert "Tournament" in rendered
        assert "entrants" in rendered

    def test_the_demo_command_runs_a_whole_cycle(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--json", "demo"]) == 0
        outcome = json.loads(capsys.readouterr().out)
        assert outcome["cycle_id"]
        assert outcome["counts"]["concepts"] > 0

    def test_the_human_demo_prints_a_readable_report(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--quiet", "demo"]) == 0
        rendered = capsys.readouterr().out
        assert "PEDRO ARTE CREATIVE MIND ENGINE" in rendered
        assert "CICLO" in rendered
        assert "Fases percorridas" in rendered

    def test_stop_persists_state(self, project_root: Path, capsys):
        assert main(["--root", str(project_root), "--mock", "--quiet", "stop"]) == 0
        assert "shutdown requested" in capsys.readouterr().out
        assert (project_root / "memory" / ".state" / "checkpoint.json").exists()

    def test_a_broken_configuration_exits_non_zero(self, project_root: Path, capsys):
        (project_root / "prompts" / "system").mkdir(parents=True, exist_ok=True)
        for path in (project_root / "prompts").rglob("*.md"):
            path.unlink()
        assert main(["--root", str(project_root), "--mock", "--quiet", "status"]) == 1
        assert "error:" in capsys.readouterr().err
