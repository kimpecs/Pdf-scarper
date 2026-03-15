"""
larry_nlp/faiss_index.py — FAISS index management.

Uses IndexFlatIP (inner product) over L2-normalised vectors
→ equivalent to exact cosine similarity search.

Files persisted to app/data/:
  faiss.index    — the FAISS binary
  faiss_ids.npy  — int array mapping index position → parts.id
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from larry_nlp.embedder import EMBEDDING_DIM

log = logging.getLogger("larry.faiss")

# ── Paths ─────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
INDEX_PATH  = _DATA_DIR / "faiss.index"
IDS_PATH    = _DATA_DIR / "faiss_ids.npy"


# ── Index wrapper ─────────────────────────────────────────────────────────
class FaissIndex:
    """
    Thin wrapper around a faiss.IndexFlatIP.

    Exposes:
        build(vectors, part_ids) — train & save
        search(query_vec, k, min_score) → list of (part_id, score)
        load() — load from disk
        is_ready() — True if index is loaded and non-empty
    """

    def __init__(self):
        self._index = None   # faiss.IndexFlatIP, loaded lazily
        self._ids:   Optional[np.ndarray] = None   # shape (N,) int64

    # ── Build ─────────────────────────────────────────────────────────────
    def build(self, vectors: np.ndarray, part_ids: list[int]) -> None:
        """
        Build (or rebuild) the index from scratch.

        vectors  — (N, EMBEDDING_DIM) float32, must be L2-normalised
        part_ids — list of integer PKs from parts table
        """
        n = len(part_ids)
        assert vectors.shape == (n, EMBEDDING_DIM), (
            f"Expected ({n}, {EMBEDDING_DIM}), got {vectors.shape}"
        )

        import faiss
        log.info("Building FAISS IndexFlatIP — %d vectors dim=%d", n, EMBEDDING_DIM)
        idx = faiss.IndexFlatIP(EMBEDDING_DIM)
        idx.add(vectors)

        ids_arr = np.array(part_ids, dtype=np.int64)

        # Persist
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(idx, str(INDEX_PATH))
        np.save(str(IDS_PATH), ids_arr)

        self._index = idx
        self._ids   = ids_arr
        log.info("FAISS index saved — %d vectors", idx.ntotal)

    # ── Load ──────────────────────────────────────────────────────────────
    def load(self) -> bool:
        """Load index from disk. Returns True if successful."""
        if not INDEX_PATH.exists() or not IDS_PATH.exists():
            log.warning("FAISS index files not found at %s", _DATA_DIR)
            return False
        try:
            import faiss
            self._index = faiss.read_index(str(INDEX_PATH))
            self._ids   = np.load(str(IDS_PATH))
            log.info("FAISS index loaded — %d vectors", self._index.ntotal)
            return True
        except Exception as e:
            log.error("Failed to load FAISS index: %s", e)
            return False

    def is_ready(self) -> bool:
        return self._index is not None and self._index.ntotal > 0

    # ── Search ────────────────────────────────────────────────────────────
    def search(
        self,
        query_vec: np.ndarray,
        k: int = 20,
        min_score: float = 0.55,
    ) -> list[tuple[int, float]]:
        """
        Search for the k nearest neighbours.

        query_vec — shape (1, EMBEDDING_DIM) float32, L2-normalised
        Returns list of (part_id, cosine_score) sorted by score DESC,
        filtered to score >= min_score.
        """
        if not self.is_ready():
            return []

        k = min(k, self._index.ntotal)
        scores, positions = self._index.search(query_vec, k)

        results = []
        for pos, score in zip(positions[0], scores[0]):
            if pos < 0:          # FAISS padding
                continue
            if score < min_score:
                break            # results are sorted DESC
            part_id = int(self._ids[pos])
            results.append((part_id, float(score)))

        return results

    # ── Incremental add ───────────────────────────────────────────────────
    def add(self, vectors: np.ndarray, part_ids: list[int]) -> None:
        """Add new vectors without rebuilding (for live ingestion)."""
        if not self.is_ready():
            self.build(vectors, part_ids)
            return

        import faiss
        self._index.add(vectors)
        new_ids = np.array(part_ids, dtype=np.int64)
        self._ids = np.concatenate([self._ids, new_ids])

        # Re-save
        faiss.write_index(self._index, str(INDEX_PATH))
        np.save(str(IDS_PATH), self._ids)
        log.debug("Added %d vectors, total=%d", len(part_ids), self._index.ntotal)


# ── Module-level singleton ────────────────────────────────────────────────
_index_singleton: Optional[FaissIndex] = None


def get_index() -> FaissIndex:
    """Return the global FaissIndex, loading from disk on first call."""
    global _index_singleton
    if _index_singleton is None:
        _index_singleton = FaissIndex()
        _index_singleton.load()
    return _index_singleton
