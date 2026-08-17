"""Persistence adapters: JSON on disk plus a dependency-free vector index."""

from creative_brain.adapters.persistence.filesystem import (
    FileAgentDecisionRepository,
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
    read_json,
    write_json_atomic,
)
from creative_brain.adapters.persistence.vector_memory import (
    InMemoryKnowledgeGraph,
    LexicalVectorMemory,
)

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
    "InMemoryKnowledgeGraph",
    "LexicalVectorMemory",
    "read_json",
    "write_json_atomic",
]
