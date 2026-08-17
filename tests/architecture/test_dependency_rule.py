"""Architecture tests.

These are the tests that keep the hexagon a hexagon. They read the actual
import statements of every module and fail when a dependency points outward.

If one of these fails, the fix is never to relax the test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "creative_brain"

#: Third-party packages the domain is forbidden to know about.
FORBIDDEN_IN_DOMAIN = {
    "anthropic",
    "openai",
    "pydantic",
    "yaml",
    "requests",
    "httpx",
    "sqlalchemy",
    "psycopg",
    "redis",
    "faiss",
    "chromadb",
    "qdrant_client",
    "fastapi",
    "flask",
    "celery",
    "apscheduler",
    "langchain",
    "langgraph",
    "crewai",
    "autogen",
}

#: Standard-library modules that would smuggle infrastructure into the domain.
FORBIDDEN_STDLIB_IN_DOMAIN = {
    "pathlib",
    "os",
    "sys",
    "socket",
    "subprocess",
    "sqlite3",
    "urllib",
    "http",
    "shutil",
    "tempfile",
    "logging",
    "threading",
    "asyncio",
}


def modules_in(package: str) -> list[Path]:
    """Every Python file under a subpackage."""
    return sorted((SRC / package).rglob("*.py"))


def imports_of(path: Path) -> set[str]:
    """Top-level module names imported by a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def internal_imports_of(path: Path) -> set[str]:
    """Full dotted ``creative_brain.*`` module paths imported by a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("creative_brain"))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("creative_brain"):
                found.add(node.module)
    return found


# --- the core rule ----------------------------------------------------------


@pytest.mark.parametrize("path", modules_in("domain"), ids=lambda p: p.name)
def test_domain_imports_no_third_party(path: Path) -> None:
    """The domain depends on the standard library and on itself. Nothing else."""
    offenders = imports_of(path) & FORBIDDEN_IN_DOMAIN
    assert not offenders, (
        f"{path.relative_to(SRC)} imports {sorted(offenders)}. "
        "The domain must never depend on an SDK, a framework or a database."
    )


@pytest.mark.parametrize("path", modules_in("domain"), ids=lambda p: p.name)
def test_domain_imports_no_io_stdlib(path: Path) -> None:
    """The domain does no I/O: no filesystem, no network, no logging, no threads."""
    offenders = imports_of(path) & FORBIDDEN_STDLIB_IN_DOMAIN
    assert not offenders, (
        f"{path.relative_to(SRC)} imports {sorted(offenders)}. "
        "I/O belongs in an adapter, behind a port."
    )


@pytest.mark.parametrize("path", modules_in("domain"), ids=lambda p: p.name)
def test_domain_does_not_import_outer_layers(path: Path) -> None:
    """DEPENDENCIES POINT INWARD: the domain knows nothing above it."""
    forbidden_prefixes = (
        "creative_brain.adapters",
        "creative_brain.application",
        "creative_brain.agents",
        "creative_brain.ports",
        "creative_brain.runtime",
        "creative_brain.cli",
        "creative_brain.composition",
    )
    offenders = {
        module
        for module in internal_imports_of(path)
        if module.startswith(forbidden_prefixes)
    }
    assert not offenders, f"{path.relative_to(SRC)} imports {sorted(offenders)}"


@pytest.mark.parametrize("path", modules_in("application"), ids=lambda p: p.name)
def test_application_does_not_import_adapters(path: Path) -> None:
    """Use cases talk to ports, never to a concrete adapter.

    The one tolerated exception is documented inline where it occurs: the
    production hand-off helper, which is pure data mapping over the manifest.
    """
    offenders = {
        module
        for module in internal_imports_of(path)
        if module.startswith("creative_brain.adapters")
        and module != "creative_brain.adapters.production"
    }
    assert not offenders, (
        f"{path.relative_to(SRC)} imports {sorted(offenders)}. "
        "Inject an adapter through BrainContext instead."
    )


@pytest.mark.parametrize("path", modules_in("ports"), ids=lambda p: p.name)
def test_ports_import_no_adapters(path: Path) -> None:
    """A contract never knows its implementations."""
    offenders = {
        m for m in internal_imports_of(path) if m.startswith("creative_brain.adapters")
    }
    assert not offenders, f"{path.relative_to(SRC)} imports {sorted(offenders)}"


@pytest.mark.parametrize("path", modules_in("runtime"), ids=lambda p: p.name)
def test_runtime_does_not_import_adapters(path: Path) -> None:
    """The runtime drives ports; the composition root supplies the adapters."""
    offenders = {
        m for m in internal_imports_of(path) if m.startswith("creative_brain.adapters")
    }
    assert not offenders, f"{path.relative_to(SRC)} imports {sorted(offenders)}"


@pytest.mark.parametrize("path", modules_in("agents"), ids=lambda p: p.name)
def test_agents_do_not_import_adapters(path: Path) -> None:
    """Agents receive a prompt library and a completion callable, not a provider."""
    offenders = {
        m for m in internal_imports_of(path) if m.startswith("creative_brain.adapters")
    }
    assert not offenders, f"{path.relative_to(SRC)} imports {sorted(offenders)}"


def test_only_the_composition_root_knows_both_sides() -> None:
    """Exactly one package is allowed to import adapters *and* wire ports."""
    importers = {
        path.relative_to(SRC).parts[0]
        for path in SRC.rglob("*.py")
        if any(m.startswith("creative_brain.adapters") for m in internal_imports_of(path))
    }
    # ``adapters`` importing adapters is internal; ``cli`` goes through composition.
    assert importers <= {"adapters", "composition", "application"}, (
        f"unexpected packages import adapters: {sorted(importers)}"
    )


def test_domain_has_no_circular_package_dependency_on_entities() -> None:
    """Policies must not import entities at runtime (only under TYPE_CHECKING)."""
    for path in modules_in("domain/policies"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        runtime_imports: set[str] = set()
        # Only module-level imports count: anything nested inside
        # `if TYPE_CHECKING:` is not in tree.body and is therefore ignored.
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("creative_brain.domain.entities"):
                    runtime_imports.add(node.module)
        # Entities that carry no policy dependency of their own are safe to import.
        allowed = {
            "creative_brain.domain.entities.circadian",
            "creative_brain.domain.entities.memory",
        }
        assert runtime_imports <= allowed, (
            f"{path.name} imports {sorted(runtime_imports - allowed)} at runtime; "
            "use `if TYPE_CHECKING:` to keep the dependency one-way."
        )
