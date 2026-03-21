"""
Thin wrapper around sentence-transformers for producing embeddings.
The model is loaded once and cached as a module-level singleton.
"""
from __future__ import annotations

from typing import List
import numpy as np

from app.config import settings

_model = None  # lazy-loaded


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Return a float32 numpy array of shape (len(texts), dim).
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,   # cosine similarity via dot product
    )
    return embeddings.astype(np.float32)


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string, returning shape (1, dim)."""
    return embed_texts([query])