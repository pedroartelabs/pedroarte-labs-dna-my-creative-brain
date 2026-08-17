"""Production hand-off adapters.

Deliberately *not* coupled to the real engines yet (Living Book, YouTube Living
Book, Living Sound, Game, Site). Only the contract and a filesystem drop exist,
so the day those engines are wired in, nothing above this line changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from creative_brain.adapters.persistence.filesystem import write_json_atomic
from creative_brain.domain.entities.project import KNOWN_ENGINES


class FilesystemProductionAdapter:
    """Drops an execution manifest where a downstream engine can pick it up."""

    def __init__(self, engine: str, outbox: Path, *, enabled: bool = False) -> None:
        self._engine = engine
        self._outbox = outbox
        self._enabled = enabled

    @property
    def engine(self) -> str:
        """Target engine name."""
        return self._engine

    def accepts(self, manifest: dict[str, Any]) -> bool:
        """Whether this engine was recommended for the project and the flag is on."""
        if not self._enabled:
            return False
        recommended = manifest.get("recommended_engines") or []
        return self._engine in recommended

    def hand_off(self, manifest: dict[str, Any]) -> str:
        """Write the manifest to the outbox; returns the receipt path."""
        project_id = str(manifest.get("project_id", "unknown"))
        target = self._outbox / self._engine / f"{project_id}.json"
        write_json_atomic(target, manifest)
        return str(target)


def suggest_engines(manifest: dict[str, Any]) -> tuple[str, ...]:
    """Pick plausible downstream engines from a project's scores.

    Heuristic and intentionally conservative — a human still decides what
    actually gets produced.
    """
    scores = manifest.get("creative_scores") or {}
    engines: list[str] = ["living_book_engine"]
    if float(scores.get("audiovisual_potential", 0)) >= 55:
        engines.append("youtube_living_book_engine")
    if float(scores.get("emotional_impact", 0)) >= 60:
        engines.append("living_sound_engine")
    if float(scores.get("expandability", 0)) >= 65:
        engines.append("game_engine")
    return tuple(e for e in engines if e in KNOWN_ENGINES)


__all__ = ["FilesystemProductionAdapter", "suggest_engines"]
