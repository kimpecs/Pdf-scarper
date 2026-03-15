"""
app/routes/search_v2.py — NLP-powered search with mandatory confidence labels.

Every result from /api/v2/search carries:
    confidence_label: "Exact match" | "Compatible alternative" | "Low confidence"
    confidence_score: float 0.0–1.0
    match_tier:       1 | 2 | 3 | 4
    match_reason:     human-readable string

FastAPI validates all responses against SearchResultOut — any result
missing confidence_label will raise a 500 before it leaves the server.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.utils.config import settings

log = logging.getLogger("larry.routes.search_v2")
router = APIRouter(prefix="/api/v2", tags=["search-v2"])

# ── Lazy orchestrator (loads FAISS + spaCy on first request) ──────────────
_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from larry_nlp.search_orchestrator import SearchOrchestrator
        db_path = settings.DB_PATH
        if not db_path.is_absolute():
            db_path = Path(__file__).resolve().parent.parent.parent / db_path
        _orchestrator = SearchOrchestrator(db_path)
        log.info("SearchOrchestrator initialised")
    return _orchestrator


# ── Pydantic response schemas ─────────────────────────────────────────────
VALID_LABELS = {"Exact match", "Compatible alternative", "Low confidence"}


class SearchResultOut(BaseModel):
    id:               int
    part_number:      str
    catalog_name:     str
    catalog_type:     Optional[str] = None
    part_type:        Optional[str] = None
    description:      Optional[str] = None
    category:         Optional[str] = None
    page:             Optional[int] = None
    image_path:       Optional[str] = None
    specifications:   Optional[object] = None
    oe_numbers:       Optional[object] = None
    applications:     Optional[object] = None
    features:         Optional[object] = None
    machine_info:     Optional[str] = None
    pdf_path:         Optional[str] = None
    review_status:    Optional[str] = None
    published:        Optional[bool] = None

    # ── Mandatory confidence fields ───────────────────────────────────────
    confidence_label: str
    confidence_score: float
    match_tier:       int
    match_reason:     str

    @field_validator("confidence_label")
    @classmethod
    def label_must_be_valid(cls, v: str) -> str:
        if v not in VALID_LABELS:
            raise ValueError(
                f"confidence_label '{v}' is not one of {VALID_LABELS}. "
                "Every search result MUST carry a valid confidence label."
            )
        return v

    @field_validator("confidence_score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        return round(v, 4)

    @field_validator("match_tier")
    @classmethod
    def tier_in_range(cls, v: int) -> int:
        if v not in (1, 2, 3, 4):
            raise ValueError("match_tier must be 1, 2, 3, or 4")
        return v

    model_config = {"extra": "allow"}


class SearchResponseOut(BaseModel):
    query:                   str
    parsed_intent:           str
    extracted_part_numbers:  list[str]
    extracted_brands:        list[str]
    extracted_part_types:    list[str]
    results:                 list[SearchResultOut]
    count:                   int
    tiers_used:              list[int]
    alias_proposals_queued:  int


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.get("/search", response_model=SearchResponseOut, summary="NLP-powered parts search")
async def nlp_search(
    q:         str   = Query(..., min_length=1, description="Natural language or part number query"),
    limit:     int   = Query(50,  ge=1, le=200),
    max_tier:  int   = Query(4,   ge=1, le=4,  description="Highest tier to use (1=ERP only, 4=all)"),
    min_score: float = Query(0.55, ge=0.0, le=1.0, description="Minimum confidence score"),
):
    """
    Natural language parts search with 4-tier fallback.

    - **Tier 1** — ERP exact match → `"Exact match"`
    - **Tier 2** — Catalog / OEM exact match → `"Exact match"`
    - **Tier 3** — Full-text keyword search → `"Compatible alternative"`
    - **Tier 4** — FAISS semantic similarity → `"Compatible alternative"` / `"Low confidence"`

    Every result carries a mandatory `confidence_label`.
    Near-duplicates (cosine ≥ 0.92) are queued as alias proposals for Data Steward review.
    """
    try:
        orchestrator = _get_orchestrator()
        raw = orchestrator.search(q, limit=limit, max_tier=max_tier)

        # Validate every result against the Pydantic schema
        validated_results = []
        for r in raw["results"]:
            if r.get("confidence_score", 0) < min_score:
                continue
            validated_results.append(SearchResultOut(**r))

        raw["results"] = validated_results
        raw["count"]   = len(validated_results)
        return SearchResponseOut(**raw)

    except Exception as e:
        log.exception("Search error for query=%r: %s", q, e)
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/search/explain", summary="Explain how a query will be parsed")
async def explain_query(
    q: str = Query(..., min_length=1, description="Query to explain"),
):
    """
    Debug endpoint: shows how Larry's NLP layer parses a query
    without executing the actual search.
    """
    from larry_nlp.ner import QueryParser
    parsed = QueryParser().parse(q)
    return {
        "raw":                  parsed.raw,
        "intent":               parsed.intent,
        "part_numbers":         parsed.part_numbers,
        "oem_numbers":          parsed.oem_numbers,
        "brands":               parsed.brands,
        "part_types":           parsed.part_types,
        "keywords":             parsed.keywords,
        "semantic_text":        parsed.to_semantic_text(),
    }


@router.get("/index/status", summary="FAISS index status")
async def index_status():
    """Check whether the FAISS semantic index is loaded and ready."""
    from larry_nlp.faiss_index import get_index
    idx = get_index()
    return {
        "ready":        idx.is_ready(),
        "vector_count": idx._index.ntotal if idx.is_ready() else 0,
        "message":      "Run python3 build_index.py to build the index." if not idx.is_ready() else "Index ready.",
    }
