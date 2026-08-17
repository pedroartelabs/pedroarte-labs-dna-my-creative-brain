"""Vector memory adapters.

The default is a dependency-free lexical index: it satisfies ``VectorMemoryPort``
exactly, so the engine has semantic-ish recall out of the box and FAISS, Chroma,
pgvector or Qdrant can replace it later without touching a use case.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from creative_brain.adapters.persistence.filesystem import read_json, write_json_atomic
from creative_brain.domain.services.similarity import tokenize
from creative_brain.ports.outbound.knowledge import VectorHit


class LexicalVectorMemory:
    """TF-IDF cosine over an in-memory index, optionally persisted to disk.

    Not a neural embedding — deliberately. It is deterministic, needs no model
    download and no API call, which is exactly what ``--mock`` and CI require.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._entries: dict[str, tuple[str, dict[str, Any]]] = {}
        self._path = path
        if path is not None:
            self._load()

    @property
    def backend(self) -> str:
        """Backend name."""
        return "lexical-tfidf"

    def index(self, key: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add or replace one entry."""
        self._entries[key] = (text, metadata or {})
        self._persist()

    def index_many(self, entries: Sequence[tuple[str, str, dict[str, Any]]]) -> None:
        """Bulk add."""
        for key, text, metadata in entries:
            self._entries[key] = (text, metadata or {})
        self._persist()

    def query(self, text: str, top_k: int = 5) -> list[VectorHit]:
        """Nearest neighbours by TF-IDF cosine, best first."""
        if not self._entries:
            return []
        idf = self._idf()
        query_vector = self._vector(text, idf)
        if not query_vector:
            return []
        hits = []
        for key, (entry_text, metadata) in self._entries.items():
            score = _cosine(query_vector, self._vector(entry_text, idf))
            if score > 0:
                hits.append(VectorHit(key=key, text=entry_text, score=score, metadata=metadata))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    def size(self) -> int:
        """Number of indexed entries."""
        return len(self._entries)

    def _idf(self) -> dict[str, float]:
        total = len(self._entries)
        document_frequency: Counter[str] = Counter()
        for text, _ in self._entries.values():
            document_frequency.update(set(tokenize(text)))
        return {
            term: math.log((total + 1) / (count + 1)) + 1.0
            for term, count in document_frequency.items()
        }

    def _vector(self, text: str, idf: dict[str, float]) -> dict[str, float]:
        counts = Counter(tokenize(text))
        if not counts:
            return {}
        length = sum(counts.values())
        return {
            term: (count / length) * idf.get(term, 1.0)
            for term, count in counts.items()
        }

    def _persist(self) -> None:
        if self._path is None:
            return
        write_json_atomic(
            self._path,
            {key: {"text": text, "metadata": meta} for key, (text, meta) in self._entries.items()},
        )

    def _load(self) -> None:
        assert self._path is not None
        raw = read_json(self._path)
        if isinstance(raw, dict):
            self._entries = {
                str(key): (str(value.get("text", "")), dict(value.get("metadata") or {}))
                for key, value in raw.items()
                if isinstance(value, dict)
            }


class InMemoryKnowledgeGraph:
    """The creative graph, kept simple: nodes, typed edges, JSON export."""

    def __init__(self, path: Path | None = None) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[tuple[str, str, str]] = []
        self._path = path

    def add_node(self, node_id: str, kind: str, attributes: dict[str, Any]) -> None:
        """Add or update a node."""
        self._nodes[node_id] = {"kind": kind, **attributes}
        self._persist()

    def add_edge(self, source: str, target: str, relation: str) -> None:
        """Connect two nodes, ignoring exact duplicates."""
        edge = (source, target, relation)
        if edge not in self._edges:
            self._edges.append(edge)
            self._persist()

    def neighbours(self, node_id: str, relation: str | None = None) -> list[str]:
        """Adjacent node ids, optionally filtered by relation."""
        return [
            target
            for source, target, rel in self._edges
            if source == node_id and (relation is None or rel == relation)
        ]

    def export(self) -> dict[str, Any]:
        """The whole graph."""
        return {
            "nodes": [{"id": node_id, **attrs} for node_id, attrs in self._nodes.items()],
            "edges": [
                {"source": s, "target": t, "relation": r} for s, t, r in self._edges
            ],
        }

    def _persist(self) -> None:
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self.export(), indent=2, ensure_ascii=False), encoding="utf-8"
            )


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    shared = set(left) & set(right)
    if not shared:
        return 0.0
    numerator = sum(left[t] * right[t] for t in shared)
    norm_left = math.sqrt(sum(v * v for v in left.values()))
    norm_right = math.sqrt(sum(v * v for v in right.values()))
    if not norm_left or not norm_right:
        return 0.0
    return round(numerator / (norm_left * norm_right), 6)


__all__ = ["InMemoryKnowledgeGraph", "LexicalVectorMemory"]
