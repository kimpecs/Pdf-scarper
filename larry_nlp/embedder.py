"""
larry_nlp/embedder.py — SentenceTransformer wrapper.

Model: all-MiniLM-L6-v2 (384-dim, ~80 MB)
  - Fast on CPU
  - Good semantic similarity for short product descriptions

Vectors are L2-normalised so inner product == cosine similarity.
"""

from __future__ import annotations

import logging
import os
from typing import Union

import numpy as np

# Must be set BEFORE torch/sentence_transformers import to prevent
# the Intel OpenMP duplicate-runtime crash on macOS (SIGSEGV in libiomp5.dylib).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

log = logging.getLogger("larry.embedder")

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ── Lazy singleton ────────────────────────────────────────────────────────
_model = None


def _get_model():
    global _model
    if _model is None:
        log.info("Loading SentenceTransformer model: %s", MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        log.info("Model loaded (dim=%d)", EMBEDDING_DIM)
    return _model


# ── Part → text ───────────────────────────────────────────────────────────
def part_to_text(part: dict) -> str:
    """
    Convert a part record to a single string for embedding.
    Field order matters — put the most discriminative fields first.
    """
    fields = [
        part.get("part_number", ""),
        part.get("description", ""),
        part.get("category", ""),
        part.get("part_type", ""),
        part.get("catalog_name", ""),
        part.get("catalog_type", ""),
    ]
    return " | ".join(f.strip() for f in fields if f and f.strip())


# ── Encode functions ──────────────────────────────────────────────────────
def encode_texts(
    texts: list[str],
    batch_size: int = 64,
    show_progress: bool = False,
) -> np.ndarray:
    """
    Encode a list of strings. Returns (N, 384) float32 array,
    L2-normalised so inner product == cosine similarity.
    """
    model = _get_model()
    vecs = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vecs.astype("float32")


def encode_query(query: str) -> np.ndarray:
    """Encode a single query string. Returns shape (1, 384)."""
    return encode_texts([query])


def encode_parts(parts: list[dict], show_progress: bool = True) -> np.ndarray:
    """Encode a list of part dicts. Returns (N, 384)."""
    texts = [part_to_text(p) for p in parts]
    return encode_texts(texts, show_progress=show_progress)
