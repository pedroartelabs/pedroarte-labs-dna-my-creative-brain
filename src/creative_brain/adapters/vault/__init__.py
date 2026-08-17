"""Obsidian vault adapter.

An Obsidian vault is a folder of markdown files — no database, no API. Notes
carry YAML frontmatter, link to each other with ``[[wikilinks]]``, and a
``.canvas`` file (JSON with nodes and edges) renders as a mind map.

That makes the vault a natural export target: the engine writes plain files and
Obsidian's graph view does the visualisation for free.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from creative_brain.ports.outbound.vault import (
    VaultCanvas,
    VaultExportReport,
    VaultNote,
)

#: Characters Obsidian (and Windows) refuse inside a file name.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, *, fallback: str = "untitled") -> str:
    """Turn an arbitrary title into a filename Obsidian will accept."""
    cleaned = _ILLEGAL.sub("", name).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or fallback


def _safe_relative_path(path: str) -> Path:
    """Sanitise every segment of a note path, keeping the folder structure.

    The application layer names notes after creative titles, which routinely
    contain characters a filesystem refuses. Cleaning them is the adapter's
    job — the use case should not have to know what a filesystem dislikes.
    """
    segments = [seg for seg in path.replace("\\", "/").split("/") if seg not in ("", ".", "..")]
    if not segments:
        return Path("untitled.md")
    *folders, filename = segments
    stem, dot, extension = filename.rpartition(".")
    if dot:
        cleaned_name = f"{safe_filename(stem)}.{extension}"
    else:
        cleaned_name = f"{safe_filename(filename)}.md"
    return Path(*[safe_filename(f) for f in folders], cleaned_name)


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in ':#[]{}&*!|>%@`"\n') or text.strip() != text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        return f'"{escaped}"'
    return text


def render_frontmatter(data: dict[str, object]) -> str:
    """Render a YAML frontmatter block. Lists become YAML sequences."""
    if not data:
        return ""
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, dict):
            if not value:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  {k}: {_yaml_scalar(v)}" for k, v in value.items())
        elif isinstance(value, (list, tuple)):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_yaml_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def render_note(note: VaultNote) -> str:
    """Render a complete markdown note: frontmatter, body, then link section."""
    parts: list[str] = []
    front = render_frontmatter(note.frontmatter)
    if front:
        parts.append(front)
    parts.append(f"# {note.title}")
    if note.body.strip():
        parts.append(note.body.strip())
    if note.links:
        parts.append("## Conexões")
        parts.append("\n".join(f"- [[{link}]]" for link in note.links))
    return "\n\n".join(parts) + "\n"


def render_canvas(canvas: VaultCanvas) -> str:
    """Render an Obsidian ``.canvas`` document (JSON with nodes and edges)."""
    nodes: list[dict[str, object]] = []
    for node in canvas.nodes:
        payload: dict[str, object] = {
            "id": node.node_id,
            "x": node.x,
            "y": node.y,
            "width": node.width,
            "height": node.height,
        }
        if node.file:
            payload["type"] = "file"
            payload["file"] = node.file
        else:
            payload["type"] = "text"
            payload["text"] = node.label
        if node.colour:
            payload["color"] = node.colour
        nodes.append(payload)

    edges: list[dict[str, object]] = []
    for edge in canvas.edges:
        payload = {
            "id": edge.edge_id,
            "fromNode": edge.from_node,
            "fromSide": "right",
            "toNode": edge.to_node,
            "toSide": "left",
        }
        if edge.label:
            payload["label"] = edge.label
        if edge.colour:
            payload["color"] = edge.colour
        edges.append(payload)

    return json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2)


class ObsidianVaultAdapter:
    """Writes notes and canvases into an Obsidian vault directory."""

    def __init__(self, vault_root: Path) -> None:
        self._root = Path(vault_root)

    @property
    def vault(self) -> str:
        """Destination path."""
        return str(self._root)

    def write_note(self, note: VaultNote) -> str:
        """Write one note, sanitising the path and creating parent folders."""
        target = self._root / _safe_relative_path(note.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_note(note), encoding="utf-8")
        return str(target)

    def write_canvas(self, canvas: VaultCanvas) -> str:
        """Write one ``.canvas`` mind map."""
        target = self._root / f"{safe_filename(canvas.name)}.canvas"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_canvas(canvas), encoding="utf-8")
        return str(target)

    def export(self, notes: list[VaultNote], canvases: list[VaultCanvas]) -> VaultExportReport:
        """Write every note and canvas in one pass."""
        written = 0
        skipped = 0
        for note in notes:
            if not note.path:
                skipped += 1
                continue
            self.write_note(note)
            written += 1
        for canvas in canvases:
            self.write_canvas(canvas)
        return VaultExportReport(
            vault_path=str(self._root),
            notes_written=written,
            canvases_written=len(canvases),
            skipped=skipped,
        )


__all__ = [
    "ObsidianVaultAdapter",
    "render_canvas",
    "render_frontmatter",
    "render_note",
    "safe_filename",
]
