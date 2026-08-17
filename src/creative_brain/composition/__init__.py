"""The composition root — the only place that knows both ports and adapters."""

from creative_brain.composition.config import BrainConfig
from creative_brain.composition.container import Brain, build_brain

__all__ = ["Brain", "BrainConfig", "build_brain"]
