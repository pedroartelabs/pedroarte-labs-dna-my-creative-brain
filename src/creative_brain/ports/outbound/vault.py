"""Vault export port.

The engine's creative graph is knowledge, not just state. A vault adapter turns
that knowledge into something a human can walk through — folders, notes and
links — without the engine knowing which note-taking tool is on the other side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class VaultNote:
    """One exportable note: frontmatter, body, and the links it points at."""

    path: str
    title: str
    body: str
    frontmatter: dict[str, object] = field(default_factory=dict)
    links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VaultCanvasNode:
    """One node on a visual map."""

    node_id: str
    label: str
    x: int
    y: int
    width: int = 260
    height: int = 100
    file: str = ""
    colour: str = ""


@dataclass(frozen=True, slots=True)
class VaultCanvasEdge:
    """One connection between two nodes."""

    edge_id: str
    from_node: str
    to_node: str
    label: str = ""
    colour: str = ""


@dataclass(frozen=True, slots=True)
class VaultCanvas:
    """A mind map: nodes positioned in space, joined by labelled edges."""

    name: str
    nodes: tuple[VaultCanvasNode, ...] = ()
    edges: tuple[VaultCanvasEdge, ...] = ()


@dataclass(frozen=True, slots=True)
class VaultExportReport:
    """What an export actually wrote."""

    vault_path: str
    notes_written: int = 0
    canvases_written: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "vault_path": self.vault_path,
            "notes_written": self.notes_written,
            "canvases_written": self.canvases_written,
            "skipped": self.skipped,
        }


@runtime_checkable
class VaultExportPort(Protocol):
    """Where the creative knowledge graph goes to be read by a human."""

    @property
    def vault(self) -> str:
        """Destination path."""
        ...

    def write_note(self, note: VaultNote) -> str:
        """Write one note; returns the location written to."""
        ...

    def write_canvas(self, canvas: VaultCanvas) -> str:
        """Write one visual map; returns the location written to."""
        ...

    def export(self, notes: list[VaultNote], canvases: list[VaultCanvas]) -> VaultExportReport:
        """Write everything in one pass."""
        ...
