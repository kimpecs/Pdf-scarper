"""
larry_nlp/alias_detector.py — Alias proposal queue.

When FAISS finds two parts with cosine similarity > ALIAS_THRESHOLD (0.92),
it proposes an alias to the review queue (alias_proposals table).

Governance rules:
  - NEVER auto-approve
  - NEVER auto-publish
  - Every proposal lands in status='pending' for Data Steward review
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("larry.alias_detector")

ALIAS_THRESHOLD = 0.92   # cosine similarity → propose alias


class AliasDetector:
    """
    Detects semantically near-duplicate parts and queues alias proposals.

    Usage:
        detector = AliasDetector(db_path)
        detector.check_and_propose(results, query_vec)
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ── Public API ────────────────────────────────────────────────────────
    def check_and_propose(
        self,
        faiss_results: list[tuple[int, float]],
        query_vec: np.ndarray,
    ) -> int:
        """
        Check FAISS results for near-duplicates and insert proposals.
        Returns the number of new proposals created.
        """
        # Only consider pairs above threshold
        high_sim = [(pid, score) for pid, score in faiss_results if score >= ALIAS_THRESHOLD]
        if len(high_sim) < 2:
            return 0

        proposed = 0
        conn = self._conn()
        try:
            for i in range(len(high_sim)):
                for j in range(i + 1, len(high_sim)):
                    src_id, src_score = high_sim[i]
                    tgt_id, tgt_score = high_sim[j]
                    avg_score = (src_score + tgt_score) / 2.0

                    if self._already_proposed(conn, src_id, tgt_id):
                        continue

                    self._insert_proposal(conn, src_id, tgt_id, avg_score)
                    proposed += 1
                    log.info(
                        "Alias proposed: part_id=%d ↔ part_id=%d  sim=%.3f",
                        src_id, tgt_id, avg_score,
                    )
            conn.commit()
        finally:
            conn.close()

        return proposed

    def propose_from_new_part(
        self,
        new_part_id: int,
        new_part_vec: np.ndarray,
        faiss_results: list[tuple[int, float]],
    ) -> int:
        """
        After ingesting a new part, check if it's a near-duplicate of
        anything already in the catalog.
        """
        conn = self._conn()
        proposed = 0
        try:
            for existing_id, score in faiss_results:
                if score < ALIAS_THRESHOLD or existing_id == new_part_id:
                    continue
                if self._already_proposed(conn, new_part_id, existing_id):
                    continue
                self._insert_proposal(conn, new_part_id, existing_id, score,
                                      reason="new_part_ingestion")
                proposed += 1
            conn.commit()
        finally:
            conn.close()
        return proposed

    def get_pending_proposals(self, limit: int = 100) -> list[dict]:
        """Fetch pending alias proposals for the Data Steward queue."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT
                    ap.id, ap.source_part_id, ap.target_part_id,
                    ap.similarity_score, ap.proposal_reason, ap.status,
                    ap.proposed_at,
                    sp.part_number AS source_part_number,
                    sp.description AS source_description,
                    sp.catalog_name AS source_catalog,
                    tp.part_number AS target_part_number,
                    tp.description AS target_description,
                    tp.catalog_name AS target_catalog
                FROM alias_proposals ap
                LEFT JOIN parts sp ON ap.source_part_id = sp.id
                LEFT JOIN parts tp ON ap.target_part_id = tp.id
                WHERE ap.status = 'pending'
                ORDER BY ap.similarity_score DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def resolve_proposal(
        self,
        proposal_id: int,
        action: str,   # 'approve' | 'reject'
        reviewer: str,
    ) -> bool:
        """Approve or reject a proposal. Returns True if found."""
        if action not in ("approve", "reject"):
            raise ValueError("action must be 'approve' or 'reject'")

        conn = self._conn()
        try:
            conn.execute("""
                UPDATE alias_proposals
                SET status = ?, reviewed_by = ?, reviewed_at = ?
                WHERE id = ? AND status = 'pending'
            """, (action + "d", reviewer, datetime.now(timezone.utc).isoformat(), proposal_id))
            conn.commit()
            return conn.execute(
                "SELECT changes()"
            ).fetchone()[0] > 0
        finally:
            conn.close()

    # ── Internals ─────────────────────────────────────────────────────────
    def _already_proposed(
        self, conn: sqlite3.Connection, id_a: int, id_b: int
    ) -> bool:
        row = conn.execute("""
            SELECT 1 FROM alias_proposals
            WHERE (source_part_id = ? AND target_part_id = ?)
               OR (source_part_id = ? AND target_part_id = ?)
        """, (id_a, id_b, id_b, id_a)).fetchone()
        return row is not None

    def _insert_proposal(
        self,
        conn: sqlite3.Connection,
        src_id: int,
        tgt_id: int,
        score: float,
        reason: str = "semantic_similarity",
    ) -> None:
        conn.execute("""
            INSERT OR IGNORE INTO alias_proposals
                (source_part_id, target_part_id, similarity_score,
                 proposal_reason, status, proposed_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (src_id, tgt_id, round(score, 4), reason,
              datetime.now(timezone.utc).isoformat()))
