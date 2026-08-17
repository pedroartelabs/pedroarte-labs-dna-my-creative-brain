"""Lexical similarity primitives.

The engine prefers a real embedding index (``VectorMemoryPort``) when one is
configured, but it must never *depend* on one: novelty, duplication and
diversity all degrade gracefully to these pure functions. That also makes them
deterministic and cheap to test.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+")

#: Portuguese + English function words. Removing them stops two unrelated ideas
#: from looking similar just because both are written in Portuguese.
STOPWORDS: frozenset[str] = frozenset(
    """
    a o e de da do das dos em no na nos nas um uma uns umas que se por para com
    como mas ou ao aos as os pelo pela sem sob sobre entre ate apos ja nao sim
    e' eh seu sua seus suas este esta isso aquilo ser estar ter haver mais menos
    muito pouco todo toda todos todas quando onde qual quais quem cujo cuja
    the of and to in a is are was were be been being for on with as by at from
    it its this that these those an or but not no yes he she they we you i
    """.split()
)


def normalise(text: str) -> str:
    """Lower-case, strip accents and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    """Content words only, accent-insensitive."""
    return [w for w in _WORD.findall(normalise(text)) if w not in STOPWORDS and len(w) > 2]


def token_set(text: str) -> frozenset[str]:
    """Unique content words of a text."""
    return frozenset(tokenize(text))


def jaccard(left: str, right: str) -> float:
    """Set overlap in 0..1. Blunt but stable — good enough to catch duplicates."""
    a, b = token_set(left), token_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cosine(left: str, right: str) -> float:
    """Bag-of-words cosine in 0..1. Sensitive to repetition, unlike Jaccard."""
    a, b = Counter(tokenize(left)), Counter(tokenize(right))
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    numerator = sum(a[t] * b[t] for t in shared)
    if not numerator:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return numerator / (norm_a * norm_b)


def similarity(left: str, right: str) -> float:
    """Blended similarity in 0..1, averaging structural and frequency overlap."""
    return round((jaccard(left, right) + cosine(left, right)) / 2, 6)


def max_similarity(text: str, corpus: list[str]) -> float:
    """The closest match in a corpus, 0..1."""
    return max((similarity(text, other) for other in corpus), default=0.0)


def nearest(text: str, corpus: dict[str, str], top: int = 3) -> list[tuple[str, float]]:
    """The ``top`` most similar corpus entries as ``(id, score)`` pairs."""
    scored = [(key, similarity(text, value)) for key, value in corpus.items()]
    return sorted(scored, key=lambda kv: kv[1], reverse=True)[:top]
