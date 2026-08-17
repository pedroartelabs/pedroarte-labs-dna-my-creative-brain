"""Prompt management port.

No important prompt may live inside the source code. Prompts are versioned
assets under ``prompts/`` with a declared purpose, inputs, outputs and
constraints — reviewable and diffable like any other artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """One versioned prompt."""

    name: str
    version: str
    purpose: str
    system: str
    user: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    constraints: tuple[str, ...] = field(default=())

    def render(self, **variables: str) -> tuple[str, str]:
        """Fill ``{placeholders}`` in both halves. Unknown placeholders stay literal."""
        return _fill(self.system, variables), _fill(self.user, variables)


@runtime_checkable
class PromptLibraryPort(Protocol):
    """Where agents get their prompts from."""

    def get(self, name: str) -> PromptTemplate:
        """Fetch a prompt by name."""
        ...

    def render(self, name: str, **variables: str) -> tuple[str, str]:
        """Fetch and render in one step; returns ``(system, user)``."""
        ...

    def names(self) -> list[str]:
        """Every prompt available."""
        ...


def _fill(text: str, variables: dict[str, str]) -> str:
    filled = text
    for key, value in variables.items():
        filled = filled.replace("{" + key + "}", str(value))
    return filled
