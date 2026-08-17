"""Controlled randomness.

Randomness helps *association* — concept collision, dream mode, mutation,
unknown-zone exploration. It never substitutes for reasoning, and it is always
seeded so a cycle can be replayed exactly.
"""

from __future__ import annotations

import random
import string
from typing import Sequence, TypeVar

T = TypeVar("T")

_ALPHABET = string.ascii_lowercase + string.digits


class SeededRandom:
    """A deterministic randomness source."""

    def __init__(self, seed: int = 20260807) -> None:
        self._seed = seed
        self._random = random.Random(seed)

    def seed(self) -> int:
        """The seed in use — recorded in every cycle manifest."""
        return self._seed

    def reseed(self, seed: int) -> None:
        """Restart the stream from a new seed."""
        self._seed = seed
        self._random = random.Random(seed)

    def token(self, length: int = 8) -> str:
        """A short lowercase token used to build entity identifiers."""
        return "".join(self._random.choice(_ALPHABET) for _ in range(max(4, length)))

    def chance(self, probability: float) -> bool:
        """True with the given probability."""
        return self._random.random() < probability

    def pick(self, items: Sequence[T]) -> T:
        """Choose one item."""
        return self._random.choice(list(items))

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        """Choose up to ``count`` distinct items."""
        pool = list(items)
        return self._random.sample(pool, min(count, len(pool)))

    def shuffled(self, items: Sequence[T]) -> list[T]:
        """A shuffled copy."""
        pool = list(items)
        self._random.shuffle(pool)
        return pool

    def uniform(self, low: float, high: float) -> float:
        """A float in ``[low, high]``."""
        return self._random.uniform(low, high)

    def gauss(self, mu: float, sigma: float) -> float:
        """A normally distributed float, used to jitter scores realistically."""
        return self._random.gauss(mu, sigma)


__all__ = ["SeededRandom"]
