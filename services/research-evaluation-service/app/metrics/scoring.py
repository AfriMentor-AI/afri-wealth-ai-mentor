"""Pluggable text-similarity backend.

The metric definitions in :mod:`app.metrics.trait_fit` and
:mod:`app.metrics.consistency` never compute similarity directly — they call a
:class:`SimilarityScorer`. v0 ships :class:`LexicalScorer`, which needs no ML
dependencies and is fully deterministic, so the suite runs in CI and its numbers
are reproducible across machines.

C2.3 replaces the backend, not the metrics::

    class EmbeddingScorer:
        def similarity(self, a: str, b: str) -> float: ...
        def similarity_matrix(self, texts: list[str]) -> list[list[float]]: ...

    report = score_dialogue(dialogue, scorer=EmbeddingScorer(model))

Because :class:`SimilarityScorer` is a ``Protocol``, any object with those two
methods satisfies it — no inheritance, no registration.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol, runtime_checkable

_TOKEN_RE = re.compile(r"[a-z0-9']+")

#: Very common words carry no persona signal; they would inflate every pairwise
#: similarity toward a constant and flatten the metric's dynamic range.
_STOPWORDS = frozenset(
    """
    a an the and or but if then than so because as of at by for with about into
    to from in on off out over under again further once here there all any both
    each few more most other some such no nor not only own same too very s t can
    will just don should now i you he she it we they me him her them my your his
    its our their this that these those am is are was were be been being have has
    had having do does did doing would could shall may might must
    """.split()
)


@runtime_checkable
class SimilarityScorer(Protocol):
    """Any object that can score text similarity in [0, 1]."""

    def similarity(self, a: str, b: str) -> float:
        """Similarity between two texts, 1.0 = identical, 0.0 = unrelated."""
        ...

    def similarity_matrix(self, texts: list[str]) -> list[list[float]]:
        """Symmetric pairwise similarity matrix with 1.0 on the diagonal."""
        ...


def tokenize(text: str, drop_stopwords: bool = True) -> list[str]:
    """Lowercase, strip punctuation, optionally drop stopwords."""
    tokens = _TOKEN_RE.findall(text.lower())
    if drop_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS]
    return tokens


def cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors. Returns 0.0 if either is empty."""
    if not vec_a or not vec_b:
        return 0.0
    shared = set(vec_a) & set(vec_b)
    if not shared:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in shared)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def cosine_dense(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two dense vectors of equal length."""
    if len(vec_a) != len(vec_b):
        raise ValueError(f"vector length mismatch: {len(vec_a)} != {len(vec_b)}")
    if not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class LexicalScorer:
    """Deterministic bag-of-words cosine scorer — the v0 default.

    Term frequencies are sublinearly scaled (``1 + log tf``) so a word repeated
    many times in one long turn cannot dominate the vector.

    This is a stand-in, and a weak one: it sees surface word overlap, not
    meaning. Two paraphrases sharing no vocabulary score ~0. Treat v0 numbers as
    a relative baseline and a plumbing check, not as ground truth about persona
    adherence — that is what C2.3's embedding backend is for.
    """

    def __init__(self, drop_stopwords: bool = True) -> None:
        self.drop_stopwords = drop_stopwords

    def _vector(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text, drop_stopwords=self.drop_stopwords))
        return {term: 1.0 + math.log(tf) for term, tf in counts.items()}

    def similarity(self, a: str, b: str) -> float:
        return round(cosine(self._vector(a), self._vector(b)), 6)

    def similarity_matrix(self, texts: list[str]) -> list[list[float]]:
        vectors = [self._vector(t) for t in texts]
        size = len(vectors)
        matrix = [[1.0] * size for _ in range(size)]
        for i in range(size):
            for j in range(i + 1, size):
                value = round(cosine(vectors[i], vectors[j]), 6)
                matrix[i][j] = matrix[j][i] = value
        return matrix


def default_scorer() -> SimilarityScorer:
    """The backend used when a caller does not supply one."""
    return LexicalScorer()
