"""
Hybrid retrieval: BM25 (keyword) + FAISS (semantic) combined.

Each chunk gets two scores:
  - BM25 score: exact/keyword match between issue tokens and chunk tokens
  - Semantic score: cosine similarity between issue embedding and chunk embedding

Both scores are min-max normalised to [0, 1] then combined:
  final_score = alpha * semantic + (1 - alpha) * bm25

Default alpha=0.5 (equal weight). Tune via RETRIEVAL_ALPHA in .env.

Optional file boost: chunks in files explicitly mentioned in the issue
get a flat +0.3 added to their final score before ranking.
"""
from __future__ import annotations

import re
import math
from typing import List, Tuple

import numpy as np

from app.config import settings
from app.schemas import CodeChunk
from app.tools.embeddings import embed_texts, embed_query

# Weight given to semantic score vs BM25. 0.0 = pure BM25, 1.0 = pure semantic.
ALPHA = 0.5
FILE_BOOST = 0.3


def _tokenise(text: str) -> List[str]:
    """
    Simple tokeniser for BM25:
    - lowercase
    - split on whitespace and punctuation
    - keep tokens of length >= 2
    """
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return [t for t in tokens if len(t) >= 2]


def _normalise(scores: List[float]) -> List[float]:
    """Min-max normalise a list of floats to [0, 1]."""
    min_s = min(scores)
    max_s = max(scores)
    span = max_s - min_s
    if span == 0:
        return [1.0] * len(scores)
    return [(s - min_s) / span for s in scores]


class ChunkIndex:
    """
    Hybrid FAISS + BM25 index over a list of CodeChunks.
    """

    def __init__(self, chunks: List[CodeChunk]):
        import faiss  # type: ignore
        from rank_bm25 import BM25Okapi  # type: ignore

        self.chunks = chunks
        tokenised = [_tokenise(c.content) for c in chunks]

        # --- BM25 ---
        self.bm25 = BM25Okapi(tokenised)

        # --- FAISS semantic index ---
        texts = [c.content for c in chunks]
        matrix = embed_texts(texts)          # (N, dim)  float32, L2-normalised
        dim = matrix.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # inner product == cosine sim
        self.index.add(matrix)

    def query(
        self,
        issue_text: str,
        top_k: int = 20,
        boost_files: List[str] | None = None,
        alpha: float = ALPHA,
    ) -> List[CodeChunk]:
        """
        Return the top_k most relevant chunks using hybrid scoring.

        alpha controls semantic vs BM25 weight:
          1.0 → pure semantic, 0.0 → pure BM25, 0.5 → equal blend
        """
        n = len(self.chunks)
        k_fetch = min(top_k * 3, n)   # over-fetch before re-ranking

        # --- BM25 scores (all N chunks) ---
        query_tokens = _tokenise(issue_text)
        bm25_raw: List[float] = self.bm25.get_scores(query_tokens).tolist()
        bm25_norm = _normalise(bm25_raw)

        # --- Semantic scores (top k_fetch from FAISS) ---
        q_emb = embed_query(issue_text)                          # (1, dim)
        distances, indices = self.index.search(q_emb, k_fetch)  # cosine sims

        # Build a dense semantic score array initialised to 0
        sem_raw = [0.0] * n
        for i, idx in enumerate(indices[0]):
            if idx >= 0:
                sem_raw[idx] = float(distances[0][i])
        sem_norm = _normalise(sem_raw)

        # --- Combine ---
        boost_set = set(boost_files) if boost_files else set()
        scored: List[Tuple[float, int]] = []
        for i in range(n):
            score = alpha * sem_norm[i] + (1 - alpha) * bm25_norm[i]
            if self.chunks[i].file_path in boost_set:
                score += FILE_BOOST
            scored.append((score, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate by chunk_id and return top_k
        seen: set[str] = set()
        result: List[CodeChunk] = []
        for _, idx in scored:
            chunk = self.chunks[idx]
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                result.append(chunk)
            if len(result) >= top_k:
                break

        return result


def extract_mentioned_files(issue_text: str, all_files: List[str]) -> List[str]:
    """
    Find files from all_files explicitly mentioned in the issue text.
    Matches on filename (with or without extension) and partial path fragments.
    """
    mentioned: List[str] = []
    issue_lower = issue_text.lower()
    for fp in all_files:
        basename = re.sub(r"\.py$", "", fp.split("/")[-1])
        if basename.lower() in issue_lower or fp.lower() in issue_lower:
            mentioned.append(fp)
    return mentioned