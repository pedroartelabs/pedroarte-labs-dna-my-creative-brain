"""Filesystem adapters: corpus ingestion and cycle output writing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from creative_brain.adapters.persistence.filesystem import read_json, write_json_atomic
from creative_brain.ports.outbound.knowledge import CorpusDocument

TEXT_SUFFIXES = {".md", ".txt", ".markdown", ".rst", ".json", ".yaml", ".yml"}

#: Directories written under every cycle root.
CYCLE_SECTIONS = (
    "observations",
    "questions",
    "seeds",
    "concepts",
    "mutations",
    "tournament",
    "finalists",
    "rejected",
    "winner",
    "genome",
    "learning",
    "runtime",
)


class FileCorpusIngestor:
    """Ingests the private creative corpus from ``input/``.

    Documents are de-duplicated by SHA-256 so re-running ingestion is free and
    idempotent. Content never leaves the machine: it is only read into memory
    and indexed locally.
    """

    MANIFEST = "_ingest_manifest.json"

    def __init__(self, input_root: Path, state_root: Path, *, clock_iso: str = "") -> None:
        self._input = input_root
        self._manifest_path = state_root / self.MANIFEST
        self._clock_iso = clock_iso
        self._documents: list[CorpusDocument] = []
        self._known: dict[str, str] = {}
        self._load_manifest()

    def ingest(self) -> list[CorpusDocument]:
        """Read everything new from ``input/``, skipping known checksums."""
        if not self._input.exists():
            return []
        fresh: list[CorpusDocument] = []
        for path in sorted(self._input.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if checksum in self._known:
                continue
            document = CorpusDocument(
                doc_id=f"doc_{checksum[:12]}",
                source=str(path.relative_to(self._input)),
                doc_type=path.suffix.lstrip(".").lower(),
                content=content,
                checksum=checksum,
                ingested_at=self._clock_iso,
                metadata={"bytes": str(len(content))},
            )
            self._known[checksum] = document.doc_id
            self._documents.append(document)
            fresh.append(document)
        self._save_manifest()
        return fresh

    def documents(self) -> list[CorpusDocument]:
        """Everything ingested in this process."""
        return list(self._documents)

    def chunk(self, document: CorpusDocument, size: int = 900) -> list[str]:
        """Split a document into overlapping-free paragraph-aligned chunks."""
        paragraphs = [p.strip() for p in document.content.split("\n\n") if p.strip()]
        chunks: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            if len(buffer) + len(paragraph) + 2 > size and buffer:
                chunks.append(buffer.strip())
                buffer = ""
            buffer += paragraph + "\n\n"
        if buffer.strip():
            chunks.append(buffer.strip())
        return chunks

    def _load_manifest(self) -> None:
        raw = read_json(self._manifest_path)
        if isinstance(raw, dict):
            self._known = {str(k): str(v) for k, v in raw.items()}

    def _save_manifest(self) -> None:
        write_json_atomic(self._manifest_path, self._known)


class FileOutputWriter:
    """Writes cycle artifacts under ``outputs/YYYY-MM-DD/cycle_<id>/``."""

    def __init__(self, outputs_root: Path, *, date_folder: str) -> None:
        self._root = outputs_root
        self._date_folder = date_folder

    def cycle_root(self, cycle_id: str) -> str:
        """Where a cycle's artifacts live."""
        return str(self._root / self._date_folder / cycle_id)

    def prepare(self, cycle_id: str) -> Path:
        """Create the cycle's directory skeleton."""
        root = Path(self.cycle_root(cycle_id))
        for section in CYCLE_SECTIONS:
            (root / section).mkdir(parents=True, exist_ok=True)
        return root

    def write(self, cycle_id: str, relative_path: str, content: str) -> str:
        """Write one text artifact."""
        target = Path(self.cycle_root(cycle_id)) / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def write_json(self, cycle_id: str, relative_path: str, payload: Any) -> str:
        """Write one JSON artifact."""
        target = Path(self.cycle_root(cycle_id)) / relative_path
        write_json_atomic(target, payload)
        return str(target)

    def write_yamlish(self, cycle_id: str, relative_path: str, payload: dict[str, Any]) -> str:
        """Write a YAML-looking artifact without depending on a YAML writer here."""
        lines = _to_yaml_lines(payload, 0)
        return self.write(cycle_id, relative_path, "\n".join(lines) + "\n")


def _to_yaml_lines(payload: Any, indent: int) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                lines.extend(_to_yaml_lines(value, indent + 1))
            elif isinstance(value, (dict, list)):
                lines.append(f"{pad}{key}: {{}}" if isinstance(value, dict) else f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {_scalar(value)}")
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                nested = _to_yaml_lines(item, indent + 1)
                lines.append(f"{pad}-")
                lines.extend(nested)
            else:
                lines.append(f"{pad}- {_scalar(item)}")
    else:
        lines.append(f"{pad}{_scalar(payload)}")
    return lines


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(ch in text for ch in ":#\n\"'") or text.strip() != text:
        return json.dumps(text, ensure_ascii=False)
    return text


__all__ = ["CYCLE_SECTIONS", "FileCorpusIngestor", "FileOutputWriter"]
