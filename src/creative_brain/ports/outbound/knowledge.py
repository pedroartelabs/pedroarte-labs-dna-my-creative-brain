"""Knowledge ports: research, corpus ingestion, vector memory, graph, production."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True, slots=True)
class ResearchQuery:
    """A request for outside knowledge."""

    topic: str
    depth: int = 1
    max_results: int = 5
    language: str = "pt-BR"
    context: str = ""


@dataclass(frozen=True, slots=True)
class ResearchResult:
    """What came back. ``sources`` may be empty for offline providers."""

    topic: str
    summary: str
    key_facts: tuple[str, ...] = ()
    implications: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    confidence: float = 50.0
    provider: str = "offline"


@runtime_checkable
class ResearchPort(Protocol):
    """Deep research on a topic the engine found interesting."""

    @property
    def provider(self) -> str:
        """Provider name."""
        ...

    def investigate(self, query: ResearchQuery) -> ResearchResult:
        """Research one topic."""
        ...


@runtime_checkable
class SearchProviderPort(Protocol):
    """Raw search, kept separate from research so either can be swapped alone."""

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Return ``[{title, url, snippet}]``."""
        ...


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """A document ingested from ``input/``: a book, a script, notes, a manifesto."""

    doc_id: str
    source: str
    doc_type: str
    content: str
    checksum: str
    ingested_at: str
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def size(self) -> int:
        """Character count."""
        return len(self.content)


@runtime_checkable
class KnowledgeSourcePort(Protocol):
    """Ingestion of the private creative corpus. Content stays local by default."""

    def ingest(self) -> list[CorpusDocument]:
        """Read everything new from the input directory, skipping known checksums."""
        ...

    def documents(self) -> list[CorpusDocument]:
        """Everything ingested so far."""
        ...

    def chunk(self, document: CorpusDocument, size: int = 900) -> list[str]:
        """Split a document into embeddable chunks."""
        ...


@dataclass(frozen=True, slots=True)
class VectorHit:
    """One nearest-neighbour result."""

    key: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorMemoryPort(Protocol):
    """Semantic memory. FAISS, Chroma, pgvector, Qdrant — or a lexical fallback."""

    @property
    def backend(self) -> str:
        """Backend name."""
        ...

    def index(self, key: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add or replace one entry."""
        ...

    def index_many(self, entries: Sequence[tuple[str, str, dict[str, Any]]]) -> None:
        """Bulk add."""
        ...

    def query(self, text: str, top_k: int = 5) -> list[VectorHit]:
        """Nearest neighbours, best first."""
        ...

    def size(self) -> int:
        """Number of indexed entries."""
        ...


@runtime_checkable
class KnowledgeGraphPort(Protocol):
    """Optional creative graph. No graph database is required to run the engine."""

    def add_node(self, node_id: str, kind: str, attributes: dict[str, Any]) -> None:
        """Add or update a node."""
        ...

    def add_edge(self, source: str, target: str, relation: str) -> None:
        """Connect two nodes."""
        ...

    def neighbours(self, node_id: str, relation: str | None = None) -> list[str]:
        """Adjacent node ids."""
        ...

    def export(self) -> dict[str, Any]:
        """The whole graph, for inspection or hand-off."""
        ...


@runtime_checkable
class CreativeProductionPort(Protocol):
    """Hand-off to a downstream production engine.

    Deliberately thin: the production engines are *not* coupled to this
    repository yet. Only the contract exists.
    """

    @property
    def engine(self) -> str:
        """Target engine name."""
        ...

    def accepts(self, manifest: dict[str, Any]) -> bool:
        """Whether this engine can produce the described project."""
        ...

    def hand_off(self, manifest: dict[str, Any]) -> str:
        """Deliver the manifest; returns a receipt/reference."""
        ...


@runtime_checkable
class OutputWriterPort(Protocol):
    """Writes cycle artifacts to durable storage."""

    def write(self, cycle_id: str, relative_path: str, content: str) -> str:
        """Write one artifact; returns the location it was written to."""
        ...

    def write_json(self, cycle_id: str, relative_path: str, payload: Any) -> str:
        """Write one JSON artifact."""
        ...

    def cycle_root(self, cycle_id: str) -> str:
        """Where a cycle's artifacts live."""
        ...
