"""Shared fixtures.

Every test runs against a throwaway project root with a FakeClock, a seeded
randomness source and the MockLLM provider — so nothing touches the network,
the real clock or the developer's own memory directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from creative_brain.adapters.clock import FakeClock
from creative_brain.adapters.llm.mock_adapter import MockLLMAdapter
from creative_brain.adapters.randomness import SeededRandom
from creative_brain.composition import Brain, build_brain

REPO_ROOT = Path(__file__).resolve().parents[1]

SEEDED_DIRECTORIES = ("config", "prompts")


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A complete, isolated project root: real config and prompts, empty memory."""
    for name in SEEDED_DIRECTORIES:
        shutil.copytree(REPO_ROOT / name, tmp_path / name)
    shutil.copytree(REPO_ROOT / "memory" / "core_dna", tmp_path / "memory" / "core_dna")
    for name in (
        "memory/evolving_dna",
        "memory/episodic",
        "memory/semantic",
        "memory/creative",
        "memory/rejected",
        "memory/successful",
        "memory/experiments",
        "memory/canon",
        "memory/graveyard",
        "memory/dead_letter",
        "outputs",
        "logs",
        "input",
    ):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def brain(project_root: Path) -> Brain:
    """A fully wired brain: fake clock, fixed seed, offline provider, no logs."""
    return build_brain(project_root, mock=True, quiet=True, fake_clock=True, seed=4242)


@pytest.fixture
def clock() -> FakeClock:
    """A clock the test owns."""
    return FakeClock()


@pytest.fixture
def random_source() -> SeededRandom:
    """A deterministic randomness source."""
    return SeededRandom(4242)


@pytest.fixture
def mock_llm(random_source: SeededRandom) -> MockLLMAdapter:
    """The offline provider."""
    return MockLLMAdapter(random_source)
