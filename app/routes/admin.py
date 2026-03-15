"""
app/routes/admin.py — Data Steward review queue for alias proposals.

Governance rules enforced here:
  - GET  /api/admin/aliases/proposals     — view pending queue
  - POST /api/admin/aliases/proposals/{id}/approve — human must explicitly approve
  - POST /api/admin/aliases/proposals/{id}/reject  — human must explicitly reject
  - GET  /api/admin/aliases             — view confirmed aliases

No auto-approve endpoint exists.  This is intentional.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.utils.config import settings

log = logging.getLogger("larry.routes.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_detector():
    from larry_nlp.alias_detector import AliasDetector
    db_path = settings.DB_PATH
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent.parent.parent / db_path
    return AliasDetector(db_path)


def _get_db():
    import sqlite3
    db_path = settings.DB_PATH
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent.parent.parent / db_path
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── Pydantic schemas ──────────────────────────────────────────────────────
class ProposalOut(BaseModel):
    id:                   int
    source_part_id:       int
    target_part_id:       int
    similarity_score:     float
    proposal_reason:      Optional[str]
    status:               str
    proposed_at:          Optional[str]
    source_part_number:   Optional[str]
    source_description:   Optional[str]
    source_catalog:       Optional[str]
    target_part_number:   Optional[str]
    target_description:   Optional[str]
    target_catalog:       Optional[str]

    model_config = {"extra": "allow"}


class ReviewAction(BaseModel):
    reviewer: str   # who is approving / rejecting (required — no anonymous actions)


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.get("/aliases/proposals", response_model=list[ProposalOut],
            summary="List pending alias proposals for review")
async def list_proposals(
    limit: int = Query(100, ge=1, le=500),
    status: str = Query("pending", description="pending | approved | rejected"),
):
    """
    Returns alias proposals queued by the AI for Data Steward review.

    These are semantically similar part pairs (cosine ≥ 0.92) that
    LARRY has flagged as potential aliases. A human must approve or
    reject each one. No auto-approval path exists.
    """
    detector = _get_detector()

    if status == "pending":
        proposals = detector.get_pending_proposals(limit=limit)
    else:
        conn = _get_db()
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
                WHERE ap.status = ?
                ORDER BY ap.similarity_score DESC
                LIMIT ?
            """, (status, limit)).fetchall()
            proposals = [dict(r) for r in rows]
        finally:
            conn.close()

    return [ProposalOut(**p) for p in proposals]


@router.post("/aliases/proposals/{proposal_id}/approve",
             summary="Approve an alias proposal (human review required)")
async def approve_proposal(proposal_id: int, body: ReviewAction):
    """
    Approve an alias proposal.  The `reviewer` field is mandatory —
    anonymous approvals are not permitted.

    This marks the proposal as **approved** and creates a confirmed alias
    in the `aliases` table for use in Tier 2 search.
    """
    if not body.reviewer or not body.reviewer.strip():
        raise HTTPException(status_code=400, detail="reviewer is required — no anonymous approvals")

    detector = _get_detector()
    ok = detector.resolve_proposal(proposal_id, "approve", body.reviewer.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="Proposal not found or already resolved")

    # Promote to confirmed aliases table
    conn = _get_db()
    try:
        proposal = conn.execute(
            "SELECT * FROM alias_proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        if proposal:
            conn.execute("""
                INSERT OR IGNORE INTO aliases
                    (part_id, alias_type, alias_value, source)
                SELECT
                    ap.target_part_id,
                    'alias',
                    sp.part_number,
                    'data_steward_approved'
                FROM alias_proposals ap
                JOIN parts sp ON ap.source_part_id = sp.id
                WHERE ap.id = ?
            """, (proposal_id,))
            conn.execute("""
                INSERT OR IGNORE INTO aliases
                    (part_id, alias_type, alias_value, source)
                SELECT
                    ap.source_part_id,
                    'alias',
                    tp.part_number,
                    'data_steward_approved'
                FROM alias_proposals ap
                JOIN parts tp ON ap.target_part_id = tp.id
                WHERE ap.id = ?
            """, (proposal_id,))
            conn.commit()
    finally:
        conn.close()

    log.info("Alias proposal %d approved by %s", proposal_id, body.reviewer)
    return {"status": "approved", "proposal_id": proposal_id, "reviewer": body.reviewer}


@router.post("/aliases/proposals/{proposal_id}/reject",
             summary="Reject an alias proposal")
async def reject_proposal(proposal_id: int, body: ReviewAction):
    """Reject an alias proposal. Reviewer name is required."""
    if not body.reviewer or not body.reviewer.strip():
        raise HTTPException(status_code=400, detail="reviewer is required")

    detector = _get_detector()
    ok = detector.resolve_proposal(proposal_id, "reject", body.reviewer.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="Proposal not found or already resolved")

    log.info("Alias proposal %d rejected by %s", proposal_id, body.reviewer)
    return {"status": "rejected", "proposal_id": proposal_id, "reviewer": body.reviewer}


@router.get("/aliases", summary="List confirmed aliases")
async def list_aliases(
    part_number: Optional[str] = Query(None, description="Filter by part number"),
    alias_type:  Optional[str] = Query(None, description="Filter by type: oe, alias, erp"),
    limit: int = Query(100, ge=1, le=500),
):
    """View all confirmed aliases in the catalog."""
    conn = _get_db()
    try:
        q = """
            SELECT a.*, p.part_number AS canonical_part_number,
                   p.catalog_name, p.description
            FROM aliases a
            JOIN parts p ON a.part_id = p.id
            WHERE 1=1
        """
        params = []
        if part_number:
            q += " AND (p.part_number LIKE ? OR a.alias_value LIKE ?)"
            params += [f"%{part_number}%", f"%{part_number}%"]
        if alias_type:
            q += " AND a.alias_type = ?"
            params.append(alias_type)
        q += " ORDER BY a.alias_type, p.part_number LIMIT ?"
        params.append(limit)

        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/stats", summary="Admin statistics")
async def admin_stats():
    """Overview of AI proposals and data quality metrics."""
    conn = _get_db()
    try:
        row = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM alias_proposals WHERE status='pending')  AS pending_proposals,
                (SELECT COUNT(*) FROM alias_proposals WHERE status='approved') AS approved_proposals,
                (SELECT COUNT(*) FROM alias_proposals WHERE status='rejected') AS rejected_proposals,
                (SELECT COUNT(*) FROM aliases)                                 AS total_aliases,
                (SELECT COUNT(*) FROM parts WHERE review_status='pending')     AS parts_pending_review,
                (SELECT COUNT(*) FROM parts WHERE review_status='approved')    AS parts_approved,
                (SELECT COUNT(*) FROM parts WHERE confidence_label='ai_extracted') AS ai_extracted_parts,
                (SELECT COUNT(*) FROM parts WHERE confidence_label='human_verified') AS human_verified_parts
        """).fetchone()
        return dict(row)
    finally:
        conn.close()
