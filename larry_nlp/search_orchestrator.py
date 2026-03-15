"""
larry_nlp/search_orchestrator.py — 4-tier search with mandatory confidence labels.

Tier 1: ERP exact match          → "Exact match"       (score 1.0)
Tier 2: Catalog OEM / part match → "Exact match"       (score 0.95)
Tier 3: SQLite LIKE / PG FTS     → "Compatible alternative" (score 0.70–0.88)
Tier 4: FAISS semantic search    → "Compatible alternative" / "Low confidence"

Every result MUST carry confidence_label.  The FastAPI layer validates this
via a Pydantic model before sending the response.

Governance: results are surfaced but never auto-approved.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from larry_nlp.ner import QueryParser, ParsedQuery
from larry_nlp.embedder import encode_query, encode_texts, part_to_text
from larry_nlp.faiss_index import FaissIndex, get_index
from larry_nlp.alias_detector import AliasDetector

log = logging.getLogger("larry.orchestrator")

# ── Confidence tiers ──────────────────────────────────────────────────────
LABEL_EXACT        = "Exact match"
LABEL_COMPATIBLE   = "Compatible alternative"
LABEL_LOW          = "Low confidence"

TIER_NAMES = {1: "ERP", 2: "Catalog", 3: "Full-text", 4: "Semantic"}

# FAISS score thresholds
SCORE_COMPATIBLE_MIN = 0.72   # above → "Compatible alternative"
SCORE_LOW_MIN        = 0.55   # above → "Low confidence"


# ── Result schema ─────────────────────────────────────────────────────────
@dataclass
class SearchResult:
    # Core fields
    id:               int
    part_number:      str
    catalog_name:     str
    catalog_type:     Optional[str]
    part_type:        Optional[str]
    description:      Optional[str]
    category:         Optional[str]
    page:             Optional[int]
    image_path:       Optional[str]
    specifications:   Optional[str]
    oe_numbers:       Optional[str]
    applications:     Optional[str]
    features:         Optional[str]
    machine_info:     Optional[str]
    pdf_path:         Optional[str]
    review_status:    Optional[str]
    published:        Optional[bool]

    # Mandatory confidence fields
    confidence_label: str              # MUST be set
    confidence_score: float            # 0.0 – 1.0
    match_tier:       int              # 1 – 4
    match_reason:     str              # human-readable

    def to_dict(self) -> dict:
        d = asdict(self)
        # Parse JSON fields for the API response
        for field_name in ("oe_numbers", "applications", "features", "specifications"):
            val = d.get(field_name)
            if val and isinstance(val, str):
                try:
                    d[field_name] = json.loads(val)
                except Exception:
                    d[field_name] = [v.strip() for v in re.split(r"[,;\n]", val) if v.strip()]
        return d


def _row_to_result(
    row: sqlite3.Row,
    confidence_label: str,
    confidence_score: float,
    tier: int,
    reason: str,
) -> SearchResult:
    d = dict(row)
    return SearchResult(
        id=d.get("id", 0),
        part_number=d.get("part_number", ""),
        catalog_name=d.get("catalog_name", ""),
        catalog_type=d.get("catalog_type"),
        part_type=d.get("part_type"),
        description=d.get("description"),
        category=d.get("category"),
        page=d.get("page"),
        image_path=d.get("image_path"),
        specifications=d.get("specifications"),
        oe_numbers=d.get("oe_numbers"),
        applications=d.get("applications"),
        features=d.get("features"),
        machine_info=d.get("machine_info"),
        pdf_path=d.get("pdf_path"),
        review_status=d.get("review_status"),
        published=bool(d.get("published", 1)),
        confidence_label=confidence_label,
        confidence_score=round(confidence_score, 4),
        match_tier=tier,
        match_reason=reason,
    )


# ── Orchestrator ──────────────────────────────────────────────────────────
class SearchOrchestrator:
    """
    Executes the 4-tier search pipeline and returns confidence-labeled results.

    db_path     — path to catalog.db
    faiss_index — FaissIndex instance (loaded or fresh)
    """

    def __init__(self, db_path: Path, faiss_index: Optional[FaissIndex] = None):
        self.db_path   = db_path
        # Pre-warm sentence_transformers BEFORE faiss loads to avoid
        # macOS OpenMP segfault when both share the same process.
        from larry_nlp.embedder import _get_model
        _get_model()
        self._faiss    = faiss_index or get_index()
        self._parser   = QueryParser()
        self._detector = AliasDetector(db_path)

    # ── Public ────────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        limit: int = 50,
        min_tier: int = 1,
        max_tier: int = 4,
    ) -> dict:
        """
        Run the full search pipeline.

        Returns a dict with:
            query, parsed_intent, results[], tiers_used[], alias_proposals_queued
        """
        if not query or not query.strip():
            return self._empty_response(query)

        parsed = self._parser.parse(query.strip())
        log.debug("Parsed query: intent=%s parts=%s brands=%s",
                  parsed.intent, parsed.part_numbers, parsed.brands)

        results: list[SearchResult] = []
        tiers_used: list[int] = []
        seen_ids: set[int] = set()

        conn = self._db()
        try:
            # ── Tier 1: ERP exact match ───────────────────────────────────
            if min_tier <= 1 <= max_tier:
                t1 = self._tier1_erp(conn, parsed)
                if t1:
                    results.extend(t1)
                    seen_ids.update(r.id for r in t1)
                    tiers_used.append(1)

            # ── Tier 2: catalog exact match ───────────────────────────────
            if min_tier <= 2 <= max_tier and len(results) < limit:
                t2 = self._tier2_catalog(conn, parsed, seen_ids)
                if t2:
                    results.extend(t2)
                    seen_ids.update(r.id for r in t2)
                    tiers_used.append(2)

            # ── Tier 3: full-text / LIKE search ──────────────────────────
            if min_tier <= 3 <= max_tier and len(results) < limit:
                t3 = self._tier3_fts(conn, parsed, seen_ids, limit - len(results))
                if t3:
                    results.extend(t3)
                    seen_ids.update(r.id for r in t3)
                    tiers_used.append(3)

            # ── Tier 4: FAISS semantic ────────────────────────────────────
            alias_proposals = 0
            if min_tier <= 4 <= max_tier and len(results) < limit:
                if self._faiss.is_ready():
                    q_vec = encode_query(parsed.to_semantic_text())
                    t4, faiss_raw = self._tier4_semantic(conn, q_vec, seen_ids, limit - len(results))
                    if t4:
                        results.extend(t4)
                        seen_ids.update(r.id for r in t4)
                        tiers_used.append(4)

                    # Alias detection (governance: never auto-approve)
                    if faiss_raw:
                        alias_proposals = self._detector.check_and_propose(faiss_raw, q_vec)
                else:
                    log.debug("FAISS index not ready — Tier 4 skipped")

        finally:
            conn.close()

        results = results[:limit]

        return {
            "query":                    query,
            "parsed_intent":            parsed.intent,
            "extracted_part_numbers":   parsed.part_numbers,
            "extracted_brands":         parsed.brands,
            "extracted_part_types":     parsed.part_types,
            "results":                  [r.to_dict() for r in results],
            "count":                    len(results),
            "tiers_used":               tiers_used,
            "alias_proposals_queued":   alias_proposals,
        }

    # ── Tier 1: ERP ───────────────────────────────────────────────────────
    def _tier1_erp(
        self, conn: sqlite3.Connection, parsed: ParsedQuery
    ) -> list[SearchResult]:
        """
        ERP exact match via the aliases table (alias_type='erp').
        In production this would query the MSSQL ERP if configured.
        """
        if not parsed.part_numbers:
            return []

        results = []
        for pn in parsed.part_numbers:
            rows = conn.execute("""
                SELECT p.* FROM parts p
                JOIN aliases a ON a.part_id = p.id
                WHERE a.alias_type = 'erp'
                  AND UPPER(a.alias_value) = UPPER(?)
                  AND p.published = 1
                LIMIT 5
            """, (pn,)).fetchall()
            for row in rows:
                results.append(_row_to_result(
                    row, LABEL_EXACT, 1.0, 1,
                    f"ERP match: {pn}"
                ))
        return results

    # ── Tier 2: catalog / OEM exact ───────────────────────────────────────
    def _tier2_catalog(
        self,
        conn: sqlite3.Connection,
        parsed: ParsedQuery,
        seen: set[int],
    ) -> list[SearchResult]:
        results = []

        all_numbers = list(dict.fromkeys(parsed.part_numbers + parsed.oem_numbers))
        if not all_numbers:
            return []

        for pn in all_numbers:
            # Direct part number match
            rows = conn.execute("""
                SELECT * FROM parts
                WHERE UPPER(part_number) = UPPER(?)
                  AND published = 1
                LIMIT 10
            """, (pn,)).fetchall()
            for row in rows:
                if row["id"] not in seen:
                    results.append(_row_to_result(
                        row, LABEL_EXACT, 0.95, 2,
                        f"Catalog match: {pn}"
                    ))
                    seen.add(row["id"])

            # OE numbers field contains this number
            oe_rows = conn.execute("""
                SELECT * FROM parts
                WHERE oe_numbers LIKE ?
                  AND id NOT IN ({})
                  AND published = 1
                LIMIT 5
            """.format(",".join("?" * len(seen)) if seen else "SELECT -1"),
                [f"%{pn}%"] + list(seen)).fetchall()
            for row in oe_rows:
                if row["id"] not in seen:
                    results.append(_row_to_result(
                        row, LABEL_EXACT, 0.92, 2,
                        f"OE number match: {pn}"
                    ))
                    seen.add(row["id"])

        return results

    # ── Tier 3: FTS / LIKE ────────────────────────────────────────────────
    def _tier3_fts(
        self,
        conn: sqlite3.Connection,
        parsed: ParsedQuery,
        seen: set[int],
        limit: int,
    ) -> list[SearchResult]:
        tokens = parsed.search_tokens()
        if not tokens:
            tokens = re.findall(r'\w+', parsed.raw)

        if not tokens:
            return []

        # Build LIKE conditions for up to 4 tokens (avoid giant queries)
        key_tokens = tokens[:4]
        like_clauses = []
        params: list = []
        for tok in key_tokens:
            like_clauses.append(
                "(part_number LIKE ? OR description LIKE ? OR category LIKE ?)"
            )
            pat = f"%{tok}%"
            params.extend([pat, pat, pat])

        where = " AND ".join(like_clauses)
        excl = ",".join("?" * len(seen)) if seen else "-1"
        params += list(seen) + [limit]

        rows = conn.execute(f"""
            SELECT * FROM parts
            WHERE ({where})
              AND id NOT IN ({excl})
              AND published = 1
            ORDER BY part_number
            LIMIT ?
        """, params).fetchall()

        results = []
        for i, row in enumerate(rows):
            score = max(0.70, 0.88 - i * 0.02)   # slight decay
            results.append(_row_to_result(
                row, LABEL_COMPATIBLE, score, 3,
                f"Text match: {', '.join(key_tokens[:2])}"
            ))
        return results

    # ── Tier 4: FAISS semantic ────────────────────────────────────────────
    def _tier4_semantic(
        self,
        conn: sqlite3.Connection,
        q_vec: np.ndarray,
        seen: set[int],
        limit: int,
    ) -> tuple[list[SearchResult], list[tuple[int, float]]]:
        raw_results = self._faiss.search(q_vec, k=limit + len(seen) + 10,
                                         min_score=SCORE_LOW_MIN)

        results = []
        kept_raw = []
        for part_id, score in raw_results:
            if part_id in seen:
                continue

            row = conn.execute(
                "SELECT * FROM parts WHERE id = ? AND published = 1", (part_id,)
            ).fetchone()
            if not row:
                continue

            if score >= SCORE_COMPATIBLE_MIN:
                label = LABEL_COMPATIBLE
            else:
                label = LABEL_LOW

            results.append(_row_to_result(
                row, label, score, 4,
                f"Semantic similarity: {score:.0%}"
            ))
            kept_raw.append((part_id, score))
            seen.add(part_id)

            if len(results) >= limit:
                break

        return results, raw_results   # return all raw for alias detection

    # ── Helpers ───────────────────────────────────────────────────────────
    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _empty_response(self, query: str) -> dict:
        return {
            "query": query,
            "parsed_intent": "search",
            "extracted_part_numbers": [],
            "extracted_brands": [],
            "extracted_part_types": [],
            "results": [],
            "count": 0,
            "tiers_used": [],
            "alias_proposals_queued": 0,
        }
