"""Prompt library adapter: versioned markdown files with YAML front matter.

File format::

    ---
    name: curiosity_agent
    version: 1.0.0
    purpose: turn observations into questions
    inputs: [observation, count]
    outputs: [questions]
    constraints:
      - never write a story
    ---

    ## SYSTEM
    ...

    ## USER
    ...
"""

from __future__ import annotations

from pathlib import Path

import yaml

from creative_brain.domain.exceptions import ConfigurationError
from creative_brain.ports.outbound.prompts import PromptTemplate

SYSTEM_MARKER = "## SYSTEM"
USER_MARKER = "## USER"


class FilePromptLibrary:
    """Loads every ``*.md`` prompt under a root directory, keyed by ``name``."""

    def __init__(
        self,
        root: Path,
        *,
        fallback: dict[str, PromptTemplate] | None = None,
        defaults: dict[str, str] | None = None,
    ) -> None:
        self._root = root
        self._templates: dict[str, PromptTemplate] = dict(fallback or {})
        self._defaults: dict[str, str] = dict(defaults or {})
        self._load()

    def get(self, name: str) -> PromptTemplate:
        """Fetch a prompt by name."""
        template = self._templates.get(name)
        if template is None:
            raise ConfigurationError(
                f"prompt '{name}' not found under {self._root}. "
                f"Available: {', '.join(sorted(self._templates)) or '(none)'}"
            )
        return template

    def render(self, name: str, **variables: str) -> tuple[str, str]:
        """Fetch and render in one step. Default variables are injected first."""
        merged = {**self._defaults, **variables}
        return self.get(name).render(**merged)

    def names(self) -> list[str]:
        """Every prompt available."""
        return sorted(self._templates)

    def _load(self) -> None:
        if not self._root.exists():
            return
        for path in sorted(self._root.rglob("*.md")):
            template = parse_prompt_file(path)
            if template is not None:
                self._templates[template.name] = template


def parse_prompt_file(path: Path) -> PromptTemplate | None:
    """Parse one prompt file, returning ``None`` when it is not a prompt.

    Read as ``utf-8-sig`` because editors on Windows happily write a BOM, and a
    BOM in front of the front matter would silently make the prompt invisible.
    """
    raw = path.read_text(encoding="utf-8-sig")
    if not raw.startswith("---"):
        return None
    _, front_matter, body = raw.split("---", 2)
    meta = yaml.safe_load(front_matter) or {}
    if not isinstance(meta, dict) or "name" not in meta:
        return None

    system, user = _split_sections(body)
    return PromptTemplate(
        name=str(meta["name"]),
        version=str(meta.get("version", "1.0.0")),
        purpose=str(meta.get("purpose", "")),
        system=system.strip(),
        user=user.strip(),
        inputs=tuple(str(i) for i in meta.get("inputs") or ()),
        outputs=tuple(str(o) for o in meta.get("outputs") or ()),
        constraints=tuple(str(c) for c in meta.get("constraints") or ()),
    )


def _split_sections(body: str) -> tuple[str, str]:
    if SYSTEM_MARKER not in body:
        return body, ""
    after_system = body.split(SYSTEM_MARKER, 1)[1]
    if USER_MARKER not in after_system:
        return after_system, ""
    system, user = after_system.split(USER_MARKER, 1)
    return system, user


__all__ = ["FilePromptLibrary", "parse_prompt_file"]
