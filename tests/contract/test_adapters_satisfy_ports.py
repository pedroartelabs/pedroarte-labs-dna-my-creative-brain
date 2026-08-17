"""Contract tests: every adapter must actually satisfy the port it claims.

``Protocol`` classes are structural, so a missing or misnamed method would only
blow up at runtime, deep inside a cycle. These tests catch it at build time.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from creative_brain.adapters.clock import FakeClock, SystemClock
from creative_brain.adapters.events import InMemoryEventBus
from creative_brain.adapters.filesystem import FileCorpusIngestor, FileOutputWriter
from creative_brain.adapters.llm.mock_adapter import MockLLMAdapter
from creative_brain.adapters.observability import InMemoryMetrics, NullLogger, StructuredLogger
from creative_brain.adapters.persistence import (
    FileCheckpointRepository,
    FileCircadianStateRepository,
    FileConceptRepository,
    FileDnaRepository,
    FileDreamRepository,
    FileMemoryRepository,
    FileObservationRepository,
    FileProjectRepository,
    FileQuestionRepository,
    FileResearchRepository,
    FileSeedRepository,
    FileTournamentRepository,
    InMemoryKnowledgeGraph,
    LexicalVectorMemory,
)
from creative_brain.adapters.production import FilesystemProductionAdapter
from creative_brain.adapters.prompts import FilePromptLibrary
from creative_brain.adapters.randomness import SeededRandom
from creative_brain.adapters.research import NullSearchProvider
from creative_brain.adapters.scheduler import InProcessScheduler
from creative_brain.adapters.vault import ObsidianVaultAdapter
from creative_brain.ports.outbound.infrastructure import (
    ClockPort,
    EventBusPort,
    LoggerPort,
    MetricsPort,
    RandomPort,
    SchedulerPort,
)
from creative_brain.ports.outbound.knowledge import (
    CreativeProductionPort,
    KnowledgeGraphPort,
    KnowledgeSourcePort,
    OutputWriterPort,
    SearchProviderPort,
    VectorMemoryPort,
)
from creative_brain.ports.outbound.llm import LLMPort
from creative_brain.ports.outbound.prompts import PromptLibraryPort
from creative_brain.ports.outbound.repositories import (
    CheckpointRepository,
    CircadianStateRepository,
    ConceptRepository,
    DnaRepository,
    DreamRepository,
    MemoryRepository,
    ObservationRepository,
    ProjectRepository,
    QuestionRepository,
    ResearchRepository,
    SeedRepository,
    TournamentRepository,
)
from creative_brain.ports.outbound.vault import VaultExportPort


def missing_members(port: type, adapter: object) -> list[str]:
    """Port members the adapter does not provide."""
    expected = [
        name
        for name, member in inspect.getmembers(port)
        if not name.startswith("_")
        and (inspect.isfunction(member) or isinstance(member, property))
    ]
    return [name for name in expected if not hasattr(adapter, name)]


def signatures_match(port: type, adapter: object) -> list[str]:
    """Methods whose parameter names diverge from the port."""
    problems: list[str] = []
    for name, member in inspect.getmembers(port, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        implementation = getattr(adapter, name, None)
        if implementation is None or not callable(implementation):
            continue
        expected = [
            p for p in inspect.signature(member).parameters if p not in {"self", "args", "kwargs"}
        ]
        actual = list(inspect.signature(implementation).parameters)
        if expected != actual:
            problems.append(f"{name}: port{expected} != adapter{actual}")
    return problems


def cases(tmp_path: Path) -> list[tuple[str, type, object]]:
    """Every (name, port, adapter) pair the system ships."""
    return [
        ("SystemClock", ClockPort, SystemClock()),
        ("FakeClock", ClockPort, FakeClock()),
        ("SeededRandom", RandomPort, SeededRandom(1)),
        ("InMemoryEventBus", EventBusPort, InMemoryEventBus()),
        ("InProcessScheduler", SchedulerPort, InProcessScheduler(FakeClock())),
        ("InMemoryMetrics", MetricsPort, InMemoryMetrics()),
        ("StructuredLogger", LoggerPort, StructuredLogger()),
        ("NullLogger", LoggerPort, NullLogger()),
        ("MockLLMAdapter", LLMPort, MockLLMAdapter(SeededRandom(1))),
        ("LexicalVectorMemory", VectorMemoryPort, LexicalVectorMemory()),
        ("InMemoryKnowledgeGraph", KnowledgeGraphPort, InMemoryKnowledgeGraph()),
        ("NullSearchProvider", SearchProviderPort, NullSearchProvider()),
        (
            "FileCorpusIngestor",
            KnowledgeSourcePort,
            FileCorpusIngestor(tmp_path / "input", tmp_path / "state"),
        ),
        (
            "FileOutputWriter",
            OutputWriterPort,
            FileOutputWriter(tmp_path / "outputs", date_folder="2026-01-01"),
        ),
        (
            "FilesystemProductionAdapter",
            CreativeProductionPort,
            FilesystemProductionAdapter("living_book_engine", tmp_path / "handoff"),
        ),
        ("FilePromptLibrary", PromptLibraryPort, FilePromptLibrary(tmp_path / "prompts")),
        ("ObsidianVaultAdapter", VaultExportPort, ObsidianVaultAdapter(tmp_path / "vault")),
        ("FileObservationRepository", ObservationRepository, FileObservationRepository(tmp_path)),
        ("FileResearchRepository", ResearchRepository, FileResearchRepository(tmp_path)),
        ("FileQuestionRepository", QuestionRepository, FileQuestionRepository(tmp_path)),
        ("FileSeedRepository", SeedRepository, FileSeedRepository(tmp_path)),
        (
            "FileConceptRepository",
            ConceptRepository,
            FileConceptRepository(tmp_path / "c", tmp_path / "g"),
        ),
        ("FileTournamentRepository", TournamentRepository, FileTournamentRepository(tmp_path)),
        ("FileProjectRepository", ProjectRepository, FileProjectRepository(tmp_path)),
        ("FileMemoryRepository", MemoryRepository, FileMemoryRepository(tmp_path)),
        ("FileDreamRepository", DreamRepository, FileDreamRepository(tmp_path)),
        ("FileDnaRepository", DnaRepository, FileDnaRepository(tmp_path, tmp_path)),
        (
            "FileCircadianStateRepository",
            CircadianStateRepository,
            FileCircadianStateRepository(tmp_path),
        ),
        ("FileCheckpointRepository", CheckpointRepository, FileCheckpointRepository(tmp_path)),
    ]


def test_every_adapter_implements_every_port_member(tmp_path: Path) -> None:
    """No adapter may be missing a method its port declares."""
    failures = {
        name: missing_members(port, adapter)
        for name, port, adapter in cases(tmp_path)
        if missing_members(port, adapter)
    }
    assert not failures, f"adapters missing port members: {failures}"


def test_every_adapter_matches_its_port_signatures(tmp_path: Path) -> None:
    """Parameter names must match, so keyword calls through a port never break."""
    failures = {
        name: signatures_match(port, adapter)
        for name, port, adapter in cases(tmp_path)
        if signatures_match(port, adapter)
    }
    assert not failures, f"signature mismatches: {failures}"


@pytest.mark.parametrize(
    "port",
    [ClockPort, RandomPort, EventBusPort, VectorMemoryPort, LLMPort],
)
def test_runtime_checkable_ports_accept_their_adapters(port: type, tmp_path: Path) -> None:
    """isinstance() against the Protocol must succeed for the shipped adapters."""
    matching = [a for _, p, a in cases(tmp_path) if p is port]
    assert matching, f"no adapter registered for {port.__name__}"
    for adapter in matching:
        assert isinstance(adapter, port)


def test_both_clocks_are_interchangeable() -> None:
    """A FakeClock must be substitutable for a SystemClock everywhere."""
    for clock in (SystemClock(), FakeClock()):
        assert clock.iso_now().endswith("Z")
        clock.sleep(0)  # must never raise
