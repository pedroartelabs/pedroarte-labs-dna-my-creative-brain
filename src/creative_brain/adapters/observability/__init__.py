"""Observability adapters: structured logging and in-process metrics."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


@dataclass
class StructuredLogger:
    """JSON-lines logger carrying correlation, cycle, project and agent ids."""

    level: str = "INFO"
    fmt: str = "json"
    context: dict[str, str] = field(default_factory=dict)
    stream: TextIO | None = None
    file_path: Path | None = None

    def bind(self, **context: str) -> StructuredLogger:
        """Return a child logger with extra context on every line."""
        return StructuredLogger(
            level=self.level,
            fmt=self.fmt,
            context={**self.context, **{k: str(v) for k, v in context.items()}},
            stream=self.stream,
            file_path=self.file_path,
        )

    def debug(self, message: str, **fields: Any) -> None:
        """Debug-level line."""
        self._emit("DEBUG", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        """Info-level line."""
        self._emit("INFO", message, fields)

    def warning(self, message: str, **fields: Any) -> None:
        """Warning-level line."""
        self._emit("WARNING", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        """Error-level line."""
        self._emit("ERROR", message, fields)

    def _emit(self, level: str, message: str, fields: dict[str, Any]) -> None:
        if LEVELS[level] < LEVELS.get(self.level.upper(), 20):
            return
        record = {"level": level, "message": message, **self.context, **fields}
        line = (
            json.dumps(record, ensure_ascii=False, default=str)
            if self.fmt == "json"
            else _as_text(record)
        )
        print(line, file=self.stream or sys.stderr)
        if self.file_path is not None:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def _as_text(record: dict[str, Any]) -> str:
    level = record.pop("level", "INFO")
    message = record.pop("message", "")
    extras = " ".join(f"{k}={v}" for k, v in record.items())
    return f"[{level:<7}] {message}" + (f"  {extras}" if extras else "")


class NullLogger:
    """A logger that swallows everything. Used in tests and quiet CLI runs."""

    def bind(self, **context: str) -> NullLogger:
        """Return itself; there is no context to carry."""
        return self

    def debug(self, message: str, **fields: Any) -> None:
        """Discard."""

    def info(self, message: str, **fields: Any) -> None:
        """Discard."""

    def warning(self, message: str, **fields: Any) -> None:
        """Discard."""

    def error(self, message: str, **fields: Any) -> None:
        """Discard."""


class InMemoryMetrics:
    """Counters, gauges and observations kept in process.

    Exporting to Prometheus/OTel is a future adapter behind the same port.
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._observations: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Add to a counter."""
        self._counters[_key(name, labels)] += value

    def gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge."""
        self._gauges[_key(name, labels)] = value

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Record a distribution sample."""
        self._observations[_key(name, labels)].append(value)

    def snapshot(self) -> dict[str, Any]:
        """Everything recorded so far, with summary statistics for observations."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "observations": {
                name: {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 4) if values else 0.0,
                    "min": round(min(values), 4) if values else 0.0,
                    "max": round(max(values), 4) if values else 0.0,
                }
                for name, values in self._observations.items()
            },
        }

    def counter(self, name: str, **labels: str) -> float:
        """Read one counter."""
        return self._counters.get(_key(name, labels), 0.0)


def _key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    rendered = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}{{{rendered}}}"


__all__ = ["InMemoryMetrics", "NullLogger", "StructuredLogger"]
