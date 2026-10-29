"""Deterministic local embeddings (spec §7.3, M2).

No model download, no network: character trigrams hashed into a fixed vector,
L2-normalised. That is enough to make the semantic term of the recall score
real (near-duplicate phrasings land close), and it keeps the store offline and
replayable. A real embedding provider can replace `embed()` without touching
the scoring weights.
"""

from __future__ import annotations

import hashlib
import math

DIM = 256
TRIGRAM_WEIGHT = 1.0
BIGRAM_WEIGHT = 0.6


def _bucket(token: str, dim: int) -> tuple[int, int]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "little")
    return value % dim, 1 if (value >> 63) & 1 else -1


def embed(text: str, *, dim: int = DIM) -> list[float]:
    """Hash n-grams into `dim` buckets. Same text always yields the same vector."""
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return [0.0] * dim
    padded = f" {normalized} "
    vector = [0.0] * dim
    for i in range(len(padded) - 2):
        tri = padded[i : i + 3]
        idx, sign = _bucket(tri, dim)
        vector[idx] += sign * TRIGRAM_WEIGHT
    for i in range(len(padded) - 1):
        bi = padded[i : i + 2]
        idx, sign = _bucket("b:" + bi, dim)
        vector[idx] += sign * BIGRAM_WEIGHT
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return [0.0] * dim
    return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def similarity(text_a: str, text_b: str) -> float:
    return max(cosine(embed(text_a), embed(text_b)), 0.0)
