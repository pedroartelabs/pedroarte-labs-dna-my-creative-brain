"""Persistence ports.

Repositories speak in domain entities. Whether that lands in JSON files,
PostgreSQL or a vector store is entirely an adapter concern.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from creative_brain.domain.entities.circadian import CircadianState
from creative_brain.domain.entities.concept import CreativeConcept
from creative_brain.domain.entities.memory import Dream, MemoryKind, MemoryRecord
from creative_brain.domain.entities.observation import CreativeObservation, ResearchFinding
from creative_brain.domain.entities.project import CreativeProject
from creative_brain.domain.entities.question import CreativeQuestion, CreativeSeed
from creative_brain.domain.entities.tournament import CreativeTournament
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.dna import CoreDna, EvolvingDna


@runtime_checkable
class ObservationRepository(Protocol):
    """Stores what the engine noticed about the world."""

    def add(self, observation: CreativeObservation) -> None:
        """Persist one observation."""
        ...

    def list_for_cycle(self, cycle_id: str) -> list[CreativeObservation]:
        """Observations captured during a cycle."""
        ...

    def recent(self, limit: int = 50) -> list[CreativeObservation]:
        """The most recent observations, newest first."""
        ...


@runtime_checkable
class ResearchRepository(Protocol):
    """Stores research findings."""

    def add(self, finding: ResearchFinding) -> None:
        """Persist one finding."""
        ...

    def list_for_cycle(self, cycle_id: str) -> list[ResearchFinding]:
        """Findings produced during a cycle."""
        ...

    def recent(self, limit: int = 50) -> list[ResearchFinding]:
        """The most recent findings, newest first."""
        ...


@runtime_checkable
class QuestionRepository(Protocol):
    """Stores creative questions — they outlive the ideas that failed to answer them."""

    def add(self, question: CreativeQuestion) -> None:
        """Persist one question."""
        ...

    def list_for_cycle(self, cycle_id: str) -> list[CreativeQuestion]:
        """Questions asked during a cycle."""
        ...

    def recent(self, limit: int = 50) -> list[CreativeQuestion]:
        """The most recent questions, newest first."""
        ...


@runtime_checkable
class SeedRepository(Protocol):
    """Stores raw creative seeds."""

    def add(self, seed: CreativeSeed) -> None:
        """Persist one seed."""
        ...

    def list_for_cycle(self, cycle_id: str) -> list[CreativeSeed]:
        """Seeds sown during a cycle."""
        ...

    def count(self) -> int:
        """Total seeds ever sown."""
        ...


@runtime_checkable
class ConceptRepository(Protocol):
    """Stores concepts across their entire lifecycle, including the graveyard."""

    def save(self, concept: CreativeConcept) -> None:
        """Insert or update a concept."""
        ...

    def get(self, concept_id: str) -> CreativeConcept | None:
        """Fetch by id."""
        ...

    def list_for_cycle(self, cycle_id: str) -> list[CreativeConcept]:
        """Every concept touched during a cycle."""
        ...

    def list_by_stage(self, stage: CreativeStage, limit: int = 200) -> list[CreativeConcept]:
        """Concepts currently in a given lifecycle stage."""
        ...

    def list_recent(self, limit: int = 200) -> list[CreativeConcept]:
        """The most recently touched concepts, whatever stage they are in."""
        ...

    def graveyard(self, limit: int = 200) -> list[CreativeConcept]:
        """Buried ideas, newest first. Nothing here is ever deleted."""
        ...

    def corpus(self, limit: int = 500) -> dict[str, str]:
        """``{concept_id: searchable text}`` used for novelty and duplicate checks."""
        ...

    def count(self) -> int:
        """Total concepts ever created."""
        ...


@runtime_checkable
class TournamentRepository(Protocol):
    """Stores tournament runs and their rounds."""

    def save(self, tournament: CreativeTournament) -> None:
        """Insert or update a tournament."""
        ...

    def get(self, tournament_id: str) -> CreativeTournament | None:
        """Fetch by id."""
        ...

    def recent(self, limit: int = 20) -> list[CreativeTournament]:
        """Recent tournaments, newest first."""
        ...


@runtime_checkable
class ProjectRepository(Protocol):
    """Stores approved projects."""

    def save(self, project: CreativeProject) -> None:
        """Insert or update a project."""
        ...

    def get(self, project_id: str) -> CreativeProject | None:
        """Fetch by id."""
        ...

    def list_all(self, limit: int = 100) -> list[CreativeProject]:
        """Every project, newest first."""
        ...

    def canon(self) -> dict[str, str]:
        """``{project_id: searchable text}`` for finished work — the strictest novelty baseline."""
        ...


@runtime_checkable
class MemoryRepository(Protocol):
    """Stores the typed memory subsystems."""

    def add(self, record: MemoryRecord) -> None:
        """Persist one record."""
        ...

    def save_all(self, records: list[MemoryRecord]) -> None:
        """Persist a batch (used after decay)."""
        ...

    def list_by_kind(self, kind: MemoryKind, limit: int = 200) -> list[MemoryRecord]:
        """Records from one memory subsystem."""
        ...

    def search(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        """Retrieve relevant records. Backed by the vector port when available."""
        ...

    def count(self) -> int:
        """Total records."""
        ...


@runtime_checkable
class DreamRepository(Protocol):
    """Stores dream sessions."""

    def add(self, dream: Dream) -> None:
        """Persist one dream."""
        ...

    def recent(self, limit: int = 20) -> list[Dream]:
        """Recent dreams, newest first."""
        ...


@runtime_checkable
class DnaRepository(Protocol):
    """Reads CORE_DNA and reads/writes EVOLVING_DNA.

    There is intentionally no ``save_core``: the protected tier is read-only to
    the engine (see ``DnaEvolutionPolicy``).
    """

    def load_core(self) -> CoreDna:
        """Read the protected identity."""
        ...

    def load_evolving(self) -> EvolvingDna:
        """Read the learned tier."""
        ...

    def save_evolving(self, dna: EvolvingDna) -> None:
        """Persist a new version of the learned tier."""
        ...


@runtime_checkable
class CircadianStateRepository(Protocol):
    """Persists the clock so a restart resumes instead of starting from zero."""

    def load(self) -> CircadianState | None:
        """Read the last checkpointed state."""
        ...

    def save(self, state: CircadianState) -> None:
        """Checkpoint the state."""
        ...


@runtime_checkable
class CheckpointRepository(Protocol):
    """Whole-runtime checkpointing: RESUME, never START FROM ZERO."""

    def save(self, payload: dict[str, Any]) -> None:
        """Write a checkpoint atomically."""
        ...

    def load(self) -> dict[str, Any] | None:
        """Read the last checkpoint, if any."""
        ...

    def clear(self) -> None:
        """Drop the checkpoint (used after a clean shutdown of a finished run)."""
        ...


@runtime_checkable
class AgentDecisionRepository(Protocol):
    """Stores decision traces: WHO decided WHAT, WHY, on which evidence."""

    def add(self, trace: dict[str, Any]) -> None:
        """Persist one trace."""
        ...

    def list_for_cycle(self, cycle_id: str) -> list[dict[str, Any]]:
        """Traces recorded during a cycle."""
        ...
