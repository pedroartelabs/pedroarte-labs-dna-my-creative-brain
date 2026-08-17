"""Filesystem-backed repositories.

JSON on disk is the right first storage: the creative artifacts stay readable
by a human, diffable in git and trivially portable. PostgreSQL, SQLite or a
document store slot in behind the same repository ports without the
application layer changing.

Writes are atomic (temp file + replace) so a crash mid-cycle never leaves a
half-written concept behind.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from creative_brain.adapters.persistence import serialization as ser
from creative_brain.domain.entities.circadian import CircadianState
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import Dream, MemoryKind, MemoryRecord
from creative_brain.domain.entities.observation import CreativeObservation, ResearchFinding
from creative_brain.domain.entities.project import CreativeProject
from creative_brain.domain.entities.question import CreativeQuestion, CreativeSeed
from creative_brain.domain.entities.tournament import CreativeTournament
from creative_brain.domain.exceptions import PersistenceFailure
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.services.similarity import similarity
from creative_brain.domain.value_objects.dna import CoreDna, EvolvingDna

T = TypeVar("T")


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON so a crash can never leave a partial file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> Any | None:
    """Read JSON, returning ``None`` for a missing or corrupt file."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PersistenceFailure(f"corrupt JSON at {path}: {exc}") from exc


@dataclass
class _JsonCollection:
    """A directory of one-file-per-entity JSON records."""

    root: Path

    def path_for(self, entity_id: str) -> Path:
        """Where one entity lives."""
        return self.root / f"{entity_id}.json"

    def save(self, entity_id: str, payload: dict[str, Any]) -> None:
        """Persist one entity."""
        write_json_atomic(self.path_for(entity_id), payload)

    def load(self, entity_id: str) -> dict[str, Any] | None:
        """Read one entity."""
        data = read_json(self.path_for(entity_id))
        return data if isinstance(data, dict) else None

    def load_all(self) -> list[dict[str, Any]]:
        """Read every entity, newest file first."""
        if not self.root.exists():
            return []
        files = sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        records = []
        for file in files:
            data = read_json(file)
            if isinstance(data, dict):
                records.append(data)
        return records

    def count(self) -> int:
        """How many entities are stored."""
        return len(list(self.root.glob("*.json"))) if self.root.exists() else 0


class FileObservationRepository:
    """Observations on disk."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def add(self, observation: CreativeObservation) -> None:
        """Persist one observation."""
        self._c.save(str(observation.id), observation.as_dict())

    def list_for_cycle(self, cycle_id: str) -> list[CreativeObservation]:
        """Observations captured during a cycle."""
        return [
            ser.observation_from_dict(r)
            for r in self._c.load_all()
            if r.get("cycle_id") == cycle_id
        ]

    def recent(self, limit: int = 50) -> list[CreativeObservation]:
        """The most recent observations."""
        return [ser.observation_from_dict(r) for r in self._c.load_all()[:limit]]


class FileResearchRepository:
    """Research findings on disk."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def add(self, finding: ResearchFinding) -> None:
        """Persist one finding."""
        self._c.save(str(finding.id), finding.as_dict())

    def list_for_cycle(self, cycle_id: str) -> list[ResearchFinding]:
        """Findings produced during a cycle."""
        return [
            ser.finding_from_dict(r) for r in self._c.load_all() if r.get("cycle_id") == cycle_id
        ]

    def recent(self, limit: int = 50) -> list[ResearchFinding]:
        """The most recent findings."""
        return [ser.finding_from_dict(r) for r in self._c.load_all()[:limit]]


class FileQuestionRepository:
    """Creative questions on disk."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def add(self, question: CreativeQuestion) -> None:
        """Persist one question."""
        self._c.save(str(question.id), question.as_dict())

    def list_for_cycle(self, cycle_id: str) -> list[CreativeQuestion]:
        """Questions asked during a cycle."""
        return [
            ser.question_from_dict(r) for r in self._c.load_all() if r.get("cycle_id") == cycle_id
        ]

    def recent(self, limit: int = 50) -> list[CreativeQuestion]:
        """The most recent questions."""
        return [ser.question_from_dict(r) for r in self._c.load_all()[:limit]]


class FileSeedRepository:
    """Creative seeds on disk."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def add(self, seed: CreativeSeed) -> None:
        """Persist one seed."""
        self._c.save(str(seed.id), seed.as_dict())

    def list_for_cycle(self, cycle_id: str) -> list[CreativeSeed]:
        """Seeds sown during a cycle."""
        return [ser.seed_from_dict(r) for r in self._c.load_all() if r.get("cycle_id") == cycle_id]

    def count(self) -> int:
        """Total seeds ever sown."""
        return self._c.count()


class FileConceptRepository:
    """Concepts on disk, across their whole lifecycle.

    A concept in the GRAVEYARD is written to *both* the working directory and
    ``memory/graveyard`` — the grave copy is the permanent record and is never
    removed, even if the working copy is later re-indexed.
    """

    def __init__(self, root: Path, graveyard_root: Path) -> None:
        self._c = _JsonCollection(root)
        self._graveyard = _JsonCollection(graveyard_root)

    def save(self, concept: CreativeConcept) -> None:
        """Insert or update a concept, mirroring buried ideas into the graveyard."""
        payload = concept.as_dict()
        self._c.save(str(concept.id), payload)
        if concept.stage is CreativeStage.GRAVEYARD:
            self._graveyard.save(str(concept.id), payload)

    def get(self, concept_id: str) -> CreativeConcept | None:
        """Fetch by id, falling back to the graveyard."""
        raw = self._c.load(concept_id) or self._graveyard.load(concept_id)
        return ser.concept_from_dict(raw) if raw else None

    def list_for_cycle(self, cycle_id: str) -> list[CreativeConcept]:
        """Every concept touched during a cycle."""
        return [
            ser.concept_from_dict(r) for r in self._c.load_all() if r.get("cycle_id") == cycle_id
        ]

    def list_by_stage(self, stage: CreativeStage, limit: int = 200) -> list[CreativeConcept]:
        """Concepts currently in a given stage."""
        return [
            ser.concept_from_dict(r)
            for r in self._c.load_all()
            if r.get("stage") == str(stage)
        ][:limit]

    def list_recent(self, limit: int = 200) -> list[CreativeConcept]:
        """The most recently touched concepts, whatever stage they are in."""
        return [ser.concept_from_dict(r) for r in self._c.load_all()[:limit]]

    def graveyard(self, limit: int = 200) -> list[CreativeConcept]:
        """Buried ideas, newest first."""
        return [ser.concept_from_dict(r) for r in self._graveyard.load_all()[:limit]]

    def corpus(self, limit: int = 500) -> dict[str, str]:
        """``{concept_id: searchable text}`` for novelty and duplicate detection."""
        corpus: dict[str, str] = {}
        for raw in self._c.load_all()[:limit]:
            corpus[str(raw.get("id"))] = " ".join(
                str(part)
                for part in (
                    raw.get("title", ""),
                    raw.get("logline", ""),
                    raw.get("central_question", ""),
                    " ".join(raw.get("themes") or []),
                )
                if part
            )
        return corpus

    def count(self) -> int:
        """Total concepts ever created."""
        return self._c.count()


class FileTournamentRepository:
    """Tournaments on disk."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def save(self, tournament: CreativeTournament) -> None:
        """Insert or update a tournament."""
        self._c.save(str(tournament.id), tournament.as_dict())

    def get(self, tournament_id: str) -> CreativeTournament | None:
        """Fetch by id."""
        raw = self._c.load(tournament_id)
        return ser.tournament_from_dict(raw) if raw else None

    def recent(self, limit: int = 20) -> list[CreativeTournament]:
        """Recent tournaments, newest first."""
        return [ser.tournament_from_dict(r) for r in self._c.load_all()[:limit]]


class FileProjectRepository:
    """Approved projects on disk. This directory is the canon."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def save(self, project: CreativeProject) -> None:
        """Insert or update a project."""
        self._c.save(str(project.id), project.as_dict())

    def get(self, project_id: str) -> CreativeProject | None:
        """Fetch by id."""
        raw = self._c.load(project_id)
        return ser.project_from_dict(raw) if raw else None

    def list_all(self, limit: int = 100) -> list[CreativeProject]:
        """Every project, newest first."""
        return [ser.project_from_dict(r) for r in self._c.load_all()[:limit]]

    def canon(self) -> dict[str, str]:
        """``{project_id: searchable text}`` for finished work."""
        return {
            str(raw.get("project_id")): " ".join(
                str(part)
                for part in (
                    raw.get("title", ""),
                    raw.get("logline", ""),
                    raw.get("central_question", ""),
                )
                if part
            )
            for raw in self._c.load_all()
        }


class FileMemoryRepository:
    """Typed memory subsystems, one directory per kind.

    Records live in a ``records/`` leaf under each subsystem. The subsystem
    directories are shared with the specialised repositories (observations,
    seeds, projects), and without the leaf this repository would try to read
    their files as memory records.
    """

    LEAF = "records"

    def __init__(self, root: Path) -> None:
        self._root = root
        self._collections = {
            kind: _JsonCollection(root / kind.value / self.LEAF) for kind in MemoryKind
        }

    def add(self, record: MemoryRecord) -> None:
        """Persist one record into its subsystem."""
        self._collections[record.kind].save(str(record.id), record.as_dict())

    def save_all(self, records: list[MemoryRecord]) -> None:
        """Persist a batch."""
        for record in records:
            self.add(record)

    def list_by_kind(self, kind: MemoryKind, limit: int = 200) -> list[MemoryRecord]:
        """Records from one subsystem."""
        return [ser.memory_from_dict(r) for r in self._collections[kind].load_all()[:limit]]

    def list_all(self, limit: int = 500) -> list[MemoryRecord]:
        """Every record across every subsystem."""
        records: list[MemoryRecord] = []
        for kind in MemoryKind:
            records.extend(self.list_by_kind(kind, limit))
        return records[:limit]

    def search(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        """Lexical retrieval. The vector adapter supersedes this when configured."""
        scored = [
            (record, similarity(query, f"{record.summary} {record.detail} {' '.join(record.tags)}"))
            for record in self.list_all()
        ]
        ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
        return [record for record, score in ranked if score > 0][:limit]

    def count(self) -> int:
        """Total records."""
        return sum(c.count() for c in self._collections.values())


class FileDreamRepository:
    """Dream sessions on disk."""

    def __init__(self, root: Path) -> None:
        self._c = _JsonCollection(root)

    def add(self, dream: Dream) -> None:
        """Persist one dream."""
        self._c.save(str(dream.id), dream.as_dict())

    def recent(self, limit: int = 20) -> list[Dream]:
        """Recent dreams, newest first."""
        return [ser.dream_from_dict(r) for r in self._c.load_all()[:limit]]


class FileDnaRepository:
    """CORE_DNA is read-only; EVOLVING_DNA is versioned on every write.

    There is deliberately no method to write the core tier. If a human wants to
    change the identity of the creative mind, they edit the file themselves.
    """

    CORE_FILE = "core_dna.json"
    EVOLVING_FILE = "evolving_dna.json"

    def __init__(self, core_root: Path, evolving_root: Path) -> None:
        self._core_root = core_root
        self._evolving_root = evolving_root

    def load_core(self) -> CoreDna:
        """Read the protected identity."""
        raw = read_json(self._core_root / self.CORE_FILE)
        if not isinstance(raw, dict):
            raise PersistenceFailure(
                f"CORE_DNA missing at {self._core_root / self.CORE_FILE}; "
                "run 'creative-brain init' or restore it from version control"
            )
        return ser.core_dna_from_dict(raw)

    def load_evolving(self) -> EvolvingDna:
        """Read the learned tier, starting empty on first run."""
        raw = read_json(self._evolving_root / self.EVOLVING_FILE)
        return ser.evolving_dna_from_dict(raw) if isinstance(raw, dict) else EvolvingDna()

    def save_evolving(self, dna: EvolvingDna) -> None:
        """Write the learned tier and keep an immutable version snapshot."""
        payload = dna.as_dict()
        write_json_atomic(self._evolving_root / self.EVOLVING_FILE, payload)
        write_json_atomic(
            self._evolving_root / "versions" / f"evolving_dna_v{dna.version:04d}.json", payload
        )


class FileCircadianStateRepository:
    """The clock's checkpoint."""

    FILE = "circadian_state.json"

    def __init__(self, root: Path) -> None:
        self._path = root / self.FILE

    def load(self) -> CircadianState | None:
        """Read the last checkpointed state."""
        raw = read_json(self._path)
        return CircadianState.from_dict(raw) if isinstance(raw, dict) else None

    def save(self, state: CircadianState) -> None:
        """Checkpoint the state."""
        write_json_atomic(self._path, state.as_dict())


class FileCheckpointRepository:
    """Whole-runtime checkpoint: RESUME, never START FROM ZERO."""

    FILE = "checkpoint.json"

    def __init__(self, root: Path) -> None:
        self._path = root / self.FILE

    def save(self, payload: dict[str, Any]) -> None:
        """Write a checkpoint atomically."""
        write_json_atomic(self._path, payload)

    def load(self) -> dict[str, Any] | None:
        """Read the last checkpoint."""
        raw = read_json(self._path)
        return raw if isinstance(raw, dict) else None

    def clear(self) -> None:
        """Remove the checkpoint after a clean, completed shutdown."""
        self._path.unlink(missing_ok=True)


class FileAgentDecisionRepository:
    """Decision traces, appended per cycle."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def add(self, trace: dict[str, Any]) -> None:
        """Append one trace to its cycle's log."""
        cycle_id = str(trace.get("cycle_id") or "unassigned")
        path = self._root / f"{cycle_id}.json"
        existing = read_json(path)
        traces = existing if isinstance(existing, list) else []
        traces.append(trace)
        write_json_atomic(path, traces)

    def list_for_cycle(self, cycle_id: str) -> list[dict[str, Any]]:
        """Traces recorded during a cycle."""
        raw = read_json(self._root / f"{cycle_id}.json")
        return raw if isinstance(raw, list) else []


def guarded(operation: Callable[[], T], context: str) -> T:
    """Run a storage operation, translating OS errors into domain failures."""
    try:
        return operation()
    except OSError as exc:
        raise PersistenceFailure(f"{context}: {exc}") from exc


__all__ = [
    "FileAgentDecisionRepository",
    "FileCheckpointRepository",
    "FileCircadianStateRepository",
    "FileConceptRepository",
    "FileDnaRepository",
    "FileDreamRepository",
    "FileMemoryRepository",
    "FileObservationRepository",
    "FileProjectRepository",
    "FileQuestionRepository",
    "FileResearchRepository",
    "FileSeedRepository",
    "FileTournamentRepository",
    "guarded",
    "read_json",
    "write_json_atomic",
]
