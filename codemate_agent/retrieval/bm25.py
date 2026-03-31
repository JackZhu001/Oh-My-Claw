"""
BM25 utilities shared by memory and retrieval layers.
"""

from __future__ import annotations

import math
import re
from typing import Any


def tokenize_text(text: str) -> list[str]:
    """Tokenize mixed Chinese/English text for lightweight retrieval."""
    return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", (text or "").lower())


def bm25_rank(
    docs: list[dict[str, Any]],
    query_tokens: list[str],
    *,
    tokens_key: str = "tokens",
) -> list[tuple[dict[str, Any], float]]:
    """Rank documents with a small BM25 implementation."""
    k1 = 1.5
    b = 0.75
    n_docs = len(docs)
    avg_len = sum(len(d.get(tokens_key, [])) for d in docs) / max(n_docs, 1)

    df: dict[str, int] = {}
    for doc in docs:
        for token in set(doc.get(tokens_key, [])):
            df[token] = df.get(token, 0) + 1

    scored: list[tuple[dict[str, Any], float]] = []
    for doc in docs:
        tokens = doc.get(tokens_key, [])
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        dl = len(tokens) or 1
        score = 0.0
        for query_token in query_tokens:
            if query_token not in tf:
                continue
            n_q = df.get(query_token, 0)
            idf = math.log(1 + (n_docs - n_q + 0.5) / (n_q + 0.5))
            freq = tf[query_token]
            denom = freq + k1 * (1 - b + b * dl / max(avg_len, 1))
            score += idf * (freq * (k1 + 1)) / denom
        scored.append((doc, score))

    return sorted(scored, key=lambda item: item[1], reverse=True)
