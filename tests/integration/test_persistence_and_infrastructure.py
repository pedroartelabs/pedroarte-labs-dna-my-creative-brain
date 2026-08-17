"""Integration tests for the adapters that actually touch state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from creative_brain.adapters.clock import FakeClock
from creative_brain.adapters.events import InMemoryEventBus
from creative_brain.adapters.filesystem import FileCorpusIngestor, FileOutputWriter
from creative_brain.adapters.llm.mock_adapter import MockLLMAdapter, stable_quality
from creative_brain.adapters.persistence import (
    FileCheckpointRepository,
    FileCircadianStateRepository,
    FileConceptRepository,
    FileDnaRepository,
    FileMemoryRepository,
    FileProjectRepository,
    LexicalVectorMemory,
)
from creative_brain.adapters.prompts import FilePromptLibrary, parse_prompt_file
from creative_brain.adapters.randomness import SeededRandom
from creative_brain.adapters.scheduler import InProcessScheduler
from creative_brain.domain.entities.circadian import CircadianState
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import MemoryKind, MemoryRecord
from creative_brain.domain.events import DomainEvent, EventName
from creative_brain.domain.exceptions import PersistenceFailure
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.dna import EvolvingDna
from creative_brain.domain.value_objects.genome import GenomeOrigin, OriginMechanism
from creative_brain.domain.value_objects.identifiers import ConceptId, MemoryId
from creative_brain.ports.outbound.llm import LLMRequest

REPO_ROOT = Path(__file__).resolve().parents[2]


def a_concept(token="aaaa1111", title="Cartório das Memórias") -> CreativeConcept:
    concept = CreativeConcept.germinate(
        concept_id=ConceptId.from_token(token),
        title=title,
        logline="uma regra nova aplicada corretamente destrói uma família",
        origin=GenomeOrigin(mechanism=OriginMechanism.COLLISION, collision=("cartório", "memória")),
        at="2026-01-01T06:00:00Z",
        cycle_id="cycle_test0001",
        themes=("memória", "herança"),
    )
    concept.pull_events()
    return concept


class TestConceptRepository:
    def test_round_trips_a_full_aggregate(self, tmp_path: Path):
        repo = FileConceptRepository(tmp_path / "c", tmp_path / "g")
        original = a_concept()
        original.advance_to(CreativeStage.CONCEPT, at="now")
        original.attach("premise", "premissa completa")
        original.pull_events()
        repo.save(original)

        restored = repo.get(str(original.id))
        assert restored is not None
        assert restored.title == original.title
        assert restored.stage is CreativeStage.CONCEPT
        assert restored.artifacts["premise"] == "premissa completa"
        assert restored.genome.origin.mechanism is OriginMechanism.COLLISION
        assert restored.themes == original.themes

    def test_burying_mirrors_into_the_graveyard(self, tmp_path: Path):
        repo = FileConceptRepository(tmp_path / "c", tmp_path / "g")
        concept = a_concept()
        concept.advance_to(CreativeStage.CONCEPT, at="now")
        concept.reject(("derivativo",), at="now")
        concept.entomb(at="now")
        concept.pull_events()
        repo.save(concept)

        buried = repo.graveyard()
        assert [c.title for c in buried] == [concept.title]
        assert buried[0].rejection_reasons == ("derivativo",)

    def test_the_corpus_is_searchable_text(self, tmp_path: Path):
        repo = FileConceptRepository(tmp_path / "c", tmp_path / "g")
        repo.save(a_concept())
        corpus = repo.corpus()
        assert "Cartório das Memórias" in next(iter(corpus.values()))

    def test_missing_concepts_return_none(self, tmp_path: Path):
        repo = FileConceptRepository(tmp_path / "c", tmp_path / "g")
        assert repo.get("concept_ffff9999") is None

    def test_writes_are_atomic(self, tmp_path: Path):
        """A crash must never leave a half-written concept behind."""
        repo = FileConceptRepository(tmp_path / "c", tmp_path / "g")
        repo.save(a_concept())
        assert not list((tmp_path / "c").glob("*.tmp"))

    def test_corrupt_json_is_reported_not_swallowed(self, tmp_path: Path):
        (tmp_path / "c").mkdir(parents=True)
        (tmp_path / "c" / "concept_bad00001.json").write_text("{not json", encoding="utf-8")
        repo = FileConceptRepository(tmp_path / "c", tmp_path / "g")
        with pytest.raises(PersistenceFailure):
            repo.list_recent()


class TestDnaRepository:
    def test_core_dna_is_read_only(self, tmp_path: Path):
        """There is deliberately no save_core: the engine cannot rewrite itself."""
        repo = FileDnaRepository(tmp_path / "core", tmp_path / "evolving")
        assert not hasattr(repo, "save_core")

    def test_missing_core_dna_fails_loudly(self, tmp_path: Path):
        repo = FileDnaRepository(tmp_path / "core", tmp_path / "evolving")
        with pytest.raises(PersistenceFailure, match="CORE_DNA"):
            repo.load_core()

    def test_the_real_core_dna_loads(self, tmp_path: Path):
        repo = FileDnaRepository(REPO_ROOT / "memory" / "core_dna", tmp_path)
        core = repo.load_core()
        assert core.identity
        assert core.principles
        assert core.forbidden_moves

    def test_evolving_dna_starts_empty_and_versions_on_write(self, tmp_path: Path):
        repo = FileDnaRepository(tmp_path / "core", tmp_path / "evolving")
        assert repo.load_evolving().version == 0

        updated = EvolvingDna().learn(discoveries=("descoberta",), reason="ciclo 1")
        repo.save_evolving(updated)
        assert repo.load_evolving().version == 1
        assert (tmp_path / "evolving" / "versions" / "evolving_dna_v0001.json").exists()


class TestCheckpointing:
    def test_the_clock_resumes_instead_of_restarting(self, tmp_path: Path):
        repo = FileCircadianStateRepository(tmp_path)
        assert repo.load() is None

        state = CircadianState()
        state.begin_cycle(cycle_id="cycle_test0001", at="now")
        state.recent_novelty = 66.0
        repo.save(state)

        restored = repo.load()
        assert restored is not None
        assert restored.cycle_id == "cycle_test0001"
        assert restored.recent_novelty == 66.0

    def test_a_checkpoint_round_trips_and_clears(self, tmp_path: Path):
        repo = FileCheckpointRepository(tmp_path)
        repo.save({"cycles_completed": 3})
        assert repo.load() == {"cycles_completed": 3}
        repo.clear()
        assert repo.load() is None


class TestMemoryRepository:
    def test_records_land_in_their_own_subsystem(self, tmp_path: Path):
        repo = FileMemoryRepository(tmp_path)
        repo.add(
            MemoryRecord(
                id=MemoryId.from_token("aaaa1111"),
                kind=MemoryKind.SEMANTIC,
                summary="princípio aprendido",
                created_at="now",
                is_principle=True,
            )
        )
        assert len(repo.list_by_kind(MemoryKind.SEMANTIC)) == 1
        assert repo.list_by_kind(MemoryKind.EPISODIC) == []

    def test_search_finds_relevant_records(self, tmp_path: Path):
        repo = FileMemoryRepository(tmp_path)
        for token, summary in (
            ("aaaa1111", "cartório registra memória como patrimônio"),
            ("bbbb2222", "peixes elétricos navegam no deserto"),
        ):
            repo.add(
                MemoryRecord(
                    id=MemoryId.from_token(token),
                    kind=MemoryKind.CREATIVE,
                    summary=summary,
                    created_at="now",
                )
            )
        hits = repo.search("memória em cartório")
        assert hits and "cartório" in hits[0].summary


class TestVectorMemory:
    def test_indexes_and_retrieves_by_meaning(self, tmp_path: Path):
        index = LexicalVectorMemory(tmp_path / "index.json")
        index.index("a", "um cartório que registra memória e herança")
        index.index("b", "peixes elétricos navegam no deserto de vidro")
        hits = index.query("herança registrada em cartório", top_k=2)
        assert hits[0].key == "a"
        assert hits[0].score > 0

    def test_survives_a_restart(self, tmp_path: Path):
        path = tmp_path / "index.json"
        LexicalVectorMemory(path).index("a", "memória herdada")
        assert LexicalVectorMemory(path).size() == 1

    def test_an_empty_index_returns_nothing(self):
        assert LexicalVectorMemory().query("qualquer coisa") == []

    def test_reindexing_replaces_rather_than_duplicates(self):
        index = LexicalVectorMemory()
        index.index("a", "primeira versão")
        index.index("a", "segunda versão")
        assert index.size() == 1


class TestEventBus:
    def test_delivers_to_named_and_wildcard_subscribers(self):
        bus = InMemoryEventBus()
        seen: list[str] = []
        bus.subscribe(str(EventName.SEED_CREATED), lambda e: seen.append("named"))
        bus.subscribe("*", lambda e: seen.append("wildcard"))
        bus.publish(DomainEvent(name=EventName.SEED_CREATED, occurred_at="now"))
        assert seen == ["named", "wildcard"]

    def test_a_failing_handler_cannot_kill_the_cycle(self):
        bus = InMemoryEventBus(max_retries=1)
        survived: list[str] = []

        def explode(_: DomainEvent) -> None:
            raise RuntimeError("boom")

        bus.subscribe("*", explode)
        bus.subscribe("*", lambda e: survived.append("ok"))
        bus.publish(DomainEvent(name=EventName.SEED_CREATED, occurred_at="now"))

        assert survived == ["ok"]
        assert len(bus.dead_letters()) == 1
        assert "boom" in bus.dead_letters()[0]["error"]

    def test_dead_letters_are_written_for_inspection(self, tmp_path: Path):
        bus = InMemoryEventBus(max_retries=0, dead_letter_dir=tmp_path)

        def explode(_: DomainEvent) -> None:
            raise RuntimeError("boom")

        bus.subscribe("*", explode)
        bus.publish(DomainEvent(name=EventName.SEED_CREATED, occurred_at="now"))
        files = list(tmp_path.glob("*.json"))
        assert files
        assert json.loads(files[0].read_text(encoding="utf-8"))["error"].startswith("RuntimeError")

    def test_history_is_recorded_in_order(self):
        bus = InMemoryEventBus()
        for name in (EventName.SEED_CREATED, EventName.CONCEPT_CREATED):
            bus.publish(DomainEvent(name=name, occurred_at="now"))
        assert [e.name for e in bus.history()] == [
            EventName.SEED_CREATED,
            EventName.CONCEPT_CREATED,
        ]


class TestScheduler:
    def test_runs_only_what_is_due(self):
        clock = FakeClock(auto_advance_seconds=0)
        scheduler = InProcessScheduler(clock)
        fired: list[str] = []
        scheduler.schedule("soon", 10, lambda: fired.append("soon"))
        scheduler.schedule("later", 1000, lambda: fired.append("later"))

        assert scheduler.run_pending() == 0
        clock.advance(20)
        assert scheduler.run_pending() == 1
        assert fired == ["soon"]
        assert scheduler.pending() == ["later"]

    def test_rescheduling_replaces_the_job(self):
        scheduler = InProcessScheduler(FakeClock(auto_advance_seconds=0))
        scheduler.schedule("job", 10, lambda: None)
        scheduler.schedule("job", 20, lambda: None)
        assert scheduler.pending() == ["job"]

    def test_cancelling_removes_it(self):
        scheduler = InProcessScheduler(FakeClock(auto_advance_seconds=0))
        scheduler.schedule("job", 10, lambda: None)
        assert scheduler.cancel("job")
        assert scheduler.pending() == []


class TestMockProvider:
    def test_every_agent_task_gets_a_structured_answer(self, mock_llm: MockLLMAdapter):
        tasks = [
            "observer.capture",
            "curiosity.questions",
            "research.investigate",
            "what_if.hypotheses",
            "collider.collide",
            "inversion.invert",
            "paradox.find",
            "unknown.propose",
            "concept.draft",
            "consequence.simulate",
            "world_architect.build",
            "character_architect.build",
            "red_team.attack",
            "blue_team.defend",
            "anti_cliche.attack",
            "judge.verdict",
            "dream.associate",
            "mutation.mutate",
            "memory.consolidate",
            "learning.reflect",
            "pitch.build",
            "synopsis.build",
        ]
        for task in tasks:
            response = mock_llm.complete(LLMRequest(task=task, system="s", user="u"))
            assert response.data, f"{task} returned nothing"
            assert response.provider == "mock"

    def test_an_unknown_task_still_answers(self, mock_llm: MockLLMAdapter):
        response = mock_llm.complete(LLMRequest(task="nope.nothing", system="s", user="u"))
        assert response.data is not None
        assert "verdict" in response.data

    def test_output_is_deterministic_for_a_given_seed(self):
        def first_title(seed: int) -> str:
            adapter = MockLLMAdapter(SeededRandom(seed))
            return adapter.complete(
                LLMRequest(task="concept.draft", system="s", user="u")
            ).data["title"]

        assert first_title(7) == first_title(7)
        assert first_title(7) != first_title(8)

    def test_pseudo_quality_is_stable_across_processes(self):
        """CRC-based, not hash()-based: replaying a cycle must give the same result."""
        assert stable_quality("um texto", "salt") == stable_quality("um texto", "salt")
        assert 0.0 <= stable_quality("qualquer coisa") <= 1.0

    def test_cost_accounting_is_populated(self, mock_llm: MockLLMAdapter):
        response = mock_llm.complete(LLMRequest(task="judge.verdict", system="s", user="u"))
        assert response.total_tokens > 0
        assert response.estimated_cost_usd > 0


class TestPromptLibrary:
    def test_the_shipped_library_loads_completely(self):
        library = FilePromptLibrary(REPO_ROOT / "prompts")
        assert len(library.names()) >= 30
        for required in ("observer_agent", "creative_judge_agent", "the_unknown_agent"):
            assert required in library.names()

    def test_every_prompt_declares_its_contract(self):
        for path in (REPO_ROOT / "prompts").rglob("*.md"):
            template = parse_prompt_file(path)
            assert template is not None, f"{path.name} is not a valid prompt"
            assert template.version, f"{path.name} has no version"
            assert template.purpose, f"{path.name} has no purpose"
            assert template.system.strip(), f"{path.name} has no system prompt"

    def test_rendering_fills_placeholders(self, tmp_path: Path):
        (tmp_path / "p.md").write_text(
            "---\nname: t\nversion: 1.0.0\npurpose: p\n---\n\n"
            "## SYSTEM\nolá {who}\n\n## USER\nfaça {what}\n",
            encoding="utf-8",
        )
        library = FilePromptLibrary(tmp_path)
        system, user = library.render("t", who="mundo", what="algo")
        assert system == "olá mundo"
        assert user == "faça algo"

    def test_a_byte_order_mark_does_not_hide_a_prompt(self, tmp_path: Path):
        """Windows editors write a BOM; a BOM must not make a prompt invisible."""
        (tmp_path / "p.md").write_text(
            "---\nname: bom\nversion: 1.0.0\npurpose: p\n---\n\n## SYSTEM\nx\n",
            encoding="utf-8-sig",
        )
        assert "bom" in FilePromptLibrary(tmp_path).names()

    def test_an_unknown_prompt_fails_with_a_useful_message(self, tmp_path: Path):
        from creative_brain.domain.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="not found"):
            FilePromptLibrary(tmp_path).get("missing")


class TestCorpusAndOutputs:
    def test_ingestion_is_idempotent_by_checksum(self, tmp_path: Path):
        source = tmp_path / "input"
        source.mkdir()
        (source / "notes.md").write_text("uma nota criativa", encoding="utf-8")

        first = FileCorpusIngestor(source, tmp_path / "state").ingest()
        assert len(first) == 1

        second = FileCorpusIngestor(source, tmp_path / "state").ingest()
        assert second == []

    def test_documents_carry_their_provenance(self, tmp_path: Path):
        source = tmp_path / "input"
        source.mkdir()
        (source / "manifesto.txt").write_text("conteúdo", encoding="utf-8")
        document = FileCorpusIngestor(source, tmp_path / "s", clock_iso="now").ingest()[0]
        assert document.source == "manifesto.txt"
        assert document.doc_type == "txt"
        assert len(document.checksum) == 64
        assert document.ingested_at == "now"

    def test_chunking_respects_paragraphs(self, tmp_path: Path):
        ingestor = FileCorpusIngestor(tmp_path / "in", tmp_path / "s")
        from creative_brain.ports.outbound.knowledge import CorpusDocument

        document = CorpusDocument(
            doc_id="d",
            source="s",
            doc_type="md",
            content="\n\n".join(["parágrafo " * 40] * 4),
            checksum="x",
            ingested_at="now",
        )
        chunks = ingestor.chunk(document, size=500)
        assert len(chunks) > 1
        assert all(chunk.strip() for chunk in chunks)

    def test_outputs_are_organised_per_cycle(self, tmp_path: Path):
        writer = FileOutputWriter(tmp_path / "outputs", date_folder="2026-08-08")
        writer.prepare("cycle_abcd1234")
        writer.write("cycle_abcd1234", "winner/concept.md", "# Conceito")
        writer.write_json("cycle_abcd1234", "winner/manifest.json", {"a": 1})
        writer.write_yamlish("cycle_abcd1234", "genome/g.yaml", {"themes": ["memória"], "d": 12.5})

        root = tmp_path / "outputs" / "2026-08-08" / "cycle_abcd1234"
        assert (root / "winner" / "concept.md").read_text(encoding="utf-8") == "# Conceito"
        assert json.loads((root / "winner" / "manifest.json").read_text(encoding="utf-8")) == {"a": 1}
        yaml_text = (root / "genome" / "g.yaml").read_text(encoding="utf-8")
        assert "themes:" in yaml_text and "- memória" in yaml_text


class TestProjectRepository:
    def test_the_canon_is_the_strictest_novelty_baseline(self, tmp_path: Path):
        from creative_brain.domain.entities.project import CreativeProject
        from creative_brain.domain.value_objects.genome import CreativeGenome
        from creative_brain.domain.value_objects.identifiers import ProjectId

        repo = FileProjectRepository(tmp_path)
        project = CreativeProject(
            id=ProjectId.from_token("aaaa1111"),
            concept_id="concept_aaaa1111",
            title="Certidão de Ausência",
            logline="uma regra que herda obrigações",
            central_question="a quem pertence?",
            genome=CreativeGenome(origin=GenomeOrigin(mechanism=OriginMechanism.PARADOX)),
            created_at="now",
            artifacts={"premise": "x"},
        )
        project.mark_production_ready(at="now", engines=("living_book_engine",))
        project.pull_events()
        repo.save(project)

        assert "Certidão de Ausência" in next(iter(repo.canon().values()))
        assert repo.get(str(project.id)).status == "PRODUCTION_READY"
