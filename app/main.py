# main.py
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import io
from pathlib import Path
import os

from app.utils.config import settings
from app.routes import health, parts
from app.routes import search_v2, admin
from app.middleware.audit_log import AuditLogMiddleware, set_session_factory

app = FastAPI(title="Larry — LIG Parts Intelligence", version="2.0.0")

# ── Audit log middleware ───────────────────────────────────────────────────
try:
    from app.services.db.session import session_factory
    set_session_factory(session_factory())
except Exception:
    pass  # Silently skip until DB is ready

app.add_middleware(AuditLogMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(parts.router)
app.include_router(search_v2.router)
app.include_router(admin.router)

# ── Static files ──────────────────────────────────────────────────────────
_static_dir    = settings.STATIC_DIR
_templates_dir = settings.TEMPLATES_DIR

if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

templates = Jinja2Templates(directory=str(_templates_dir))


# ── Helpers ───────────────────────────────────────────────────────────────

def get_db_connection() -> sqlite3.Connection:
    db_path = settings.DB_PATH
    if not db_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        db_path = project_root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def resolve_image_path(raw_path: str) -> Optional[Path]:
    """Try several path strategies and return the first one that exists."""
    project_root = Path(__file__).resolve().parent.parent
    p = Path(raw_path)
    candidates = [
        p,
        project_root / p,
        project_root / "app" / p,
        project_root / "app" / "data" / "part_images" / p.name,
    ]
    return next((c for c in candidates if c.exists()), None)


# ── Pydantic models ───────────────────────────────────────────────────────

class PartBase(BaseModel):
    id: int
    catalog_name: str
    part_number: str
    description: Optional[str] = None
    category: Optional[str] = None
    page: Optional[int] = None

class PartDetail(PartBase):
    catalog_type: Optional[str] = None
    part_type: Optional[str] = None
    image_path: Optional[str] = None
    machine_info: Optional[str] = None
    specifications: Optional[str] = None
    oe_numbers: Optional[str] = None
    applications: Optional[str] = None
    features: Optional[str] = None
    created_at: Optional[str] = None

class ImageInfo(BaseModel):
    id: int
    image_filename: str
    image_type: str
    image_width: int
    image_height: int
    file_size: int
    page_number: int
    confidence: float

class TechnicalGuide(BaseModel):
    id: int
    guide_name: str
    display_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    pdf_path: Optional[str] = None
    is_active: bool
    part_count: int

class SearchResponse(BaseModel):
    parts: List[PartBase]
    total_count: int
    page: int
    page_size: int


# ==========================================================================
# FRONTEND / ROOT
# ==========================================================================

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_file = Path("app/static/index.html")
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="""
        <!DOCTYPE html><html><head><title>Parts Catalog</title></head>
        <body>
            <h1>Parts Catalog</h1>
            <p style="color:red">Warning: index.html not found in app/static/</p>
            <p><a href="/docs">API Documentation</a></p>
        </body></html>
    """)


# ==========================================================================
# CONFIG  (static — must be before any /{variable} route at same prefix)
# ==========================================================================

@app.get("/api/config")
async def get_config():
    return {
        "maxDescriptionLength": 120,
        "maxApplicationsDisplay": 2,
        "searchDebounceMs": 300,
        "enableTechnicalGuides": True,
        "maxSearchResults": 50,
    }


# ==========================================================================
# SEARCH
# ==========================================================================

@app.get("/api/search")
async def api_search_parts(
    q: str = Query("", min_length=0),
    category: str = Query(""),
    part_type: str = Query(""),
    catalog_type: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
):
    conn = get_db_connection()
    try:
        where_conditions, params = [], []

        if q and q.strip():
            where_conditions.append("(p.part_number LIKE ? OR p.description LIKE ?)")
            term = f"%{q}%"
            params.extend([term, term])
        if category and category.strip():
            where_conditions.append("p.category = ?")
            params.append(category)
        if part_type and part_type.strip():
            where_conditions.append("p.part_type = ?")
            params.append(part_type)
        if catalog_type and catalog_type.strip():
            where_conditions.append("p.catalog_name = ?")
            params.append(catalog_type)

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        sql = f"""
            SELECT p.*,
                   (SELECT COUNT(*) FROM part_images pi WHERE pi.part_id = p.id) AS image_count
            FROM parts p
            {where_clause}
            ORDER BY p.part_number
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return {"query": q, "results": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/search")
async def search_parts(
    q: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=200),
):
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT p.*, snippet(parts_fts, 2, '<b>', '</b>', '...', 64) AS snippet
            FROM parts_fts
            JOIN parts p ON p.id = parts_fts.rowid
            WHERE parts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (f'"{q}"*', limit)).fetchall()
        return {"query": q, "results": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


# ==========================================================================
# ANALYTICS
# ==========================================================================

@app.get("/api/analytics/categories")
async def api_get_categories():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT category, COUNT(*) AS part_count
            FROM parts
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY part_count DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/analytics/catalogs")
async def api_get_catalogs():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT catalog_name, COUNT(*) AS part_count
            FROM parts
            WHERE catalog_name IS NOT NULL AND catalog_name != ''
            GROUP BY catalog_name
            ORDER BY part_count DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/analytics/catalogs")
async def get_catalog_analytics():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT
                catalog_name,
                COUNT(*) AS part_count,
                COUNT(DISTINCT part_number) AS unique_part_numbers,
                COUNT(DISTINCT category) AS category_count,
                ROUND(COUNT(image_path) * 100.0 / COUNT(*), 2) AS image_coverage_percent
            FROM parts
            GROUP BY catalog_name
            ORDER BY part_count DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/analytics/categories")
async def get_category_analytics():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT
                category,
                COUNT(*) AS part_count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM parts), 2) AS percentage
            FROM parts
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY part_count DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/analytics/dashboard")
async def get_dashboard_stats():
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM parts)                              AS total_parts,
                (SELECT COUNT(*) FROM part_images)                        AS total_images,
                (SELECT COUNT(*) FROM technical_guides)                   AS total_guides,
                (SELECT COUNT(*) FROM part_guides)                        AS total_associations,
                (SELECT COUNT(*) FROM parts WHERE image_path IS NOT NULL) AS parts_with_image_reference,
                (SELECT COUNT(DISTINCT part_id) FROM part_images)         AS unique_parts_with_images
        """).fetchone()
        return dict(row)
    finally:
        conn.close()


# ==========================================================================
# PARTS  — IMPORTANT: static sub-paths BEFORE /{part_id} dynamic routes
# ==========================================================================

@app.get("/api/parts/types")
async def get_part_types():
    """Return all distinct part types. Must be above /api/parts/{part_id}."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT DISTINCT part_type FROM parts
            WHERE part_type IS NOT NULL AND part_type != ''
            ORDER BY part_type
        """).fetchall()
        return {"part_types": [r[0] for r in rows]}
    finally:
        conn.close()


@app.get("/parts", response_model=SearchResponse)
async def get_parts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    catalog: Optional[str] = None,
    category: Optional[str] = None,
):
    conn = get_db_connection()
    try:
        offset = (page - 1) * page_size
        where_conditions, params = [], []

        if catalog:
            where_conditions.append("catalog_name = ?")
            params.append(catalog)
        if category:
            where_conditions.append("category = ?")
            params.append(category)

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        total_count = conn.execute(
            f"SELECT COUNT(*) FROM parts {where_clause}", params
        ).fetchone()[0]

        sql = f"""
            SELECT p.*,
                   (SELECT COUNT(*) FROM part_images pi WHERE pi.part_id = p.id) AS image_count,
                   (SELECT COUNT(*) FROM part_guides pg  WHERE pg.part_id  = p.id) AS guide_count
            FROM parts p
            {where_clause}
            ORDER BY p.id
            LIMIT ? OFFSET ?
        """
        params.extend([page_size, offset])
        rows = conn.execute(sql, params).fetchall()

        return SearchResponse(
            parts=[dict(r) for r in rows],
            total_count=total_count,
            page=page,
            page_size=page_size,
        )
    finally:
        conn.close()


@app.get("/parts/search/{part_number}")
async def search_part_by_number(part_number: str):
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT p.*,
                   GROUP_CONCAT(DISTINCT pi.image_filename) AS images,
                   GROUP_CONCAT(DISTINCT tg.display_name)   AS guides
            FROM parts p
            LEFT JOIN part_images pi ON p.id = pi.part_id
            LEFT JOIN part_guides  pg ON p.id = pg.part_id
            LEFT JOIN technical_guides tg ON pg.guide_id = tg.id
            WHERE p.part_number = ?
            GROUP BY p.id
        """, (part_number,)).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Part not found")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/parts/{part_id}/images")
async def get_part_images(part_id: int):
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM part_images
            WHERE part_id = ?
            ORDER BY confidence DESC, created_at DESC
        """, (part_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/parts/{part_id}/guides")
async def get_part_guides(part_id: int):
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT tg.*, pg.confidence_score
            FROM technical_guides tg
            JOIN part_guides pg ON tg.id = pg.guide_id
            WHERE pg.part_id = ?
            ORDER BY pg.confidence_score DESC
        """, (part_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/parts/{part_id}", response_model=PartDetail)
async def get_part(part_id: int):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Part not found")
        return dict(row)
    finally:
        conn.close()


# ── /api/parts/* — same ordering rule applies ─────────────────────────────

@app.get("/api/parts/{part_id}/guides")
async def api_get_part_guides(part_id: int):
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT tg.*, pg.confidence_score
            FROM technical_guides tg
            JOIN part_guides pg ON tg.id = pg.guide_id
            WHERE pg.part_id = ?
            ORDER BY pg.confidence_score DESC
        """, (part_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/parts/{part_id}")
async def api_get_part(part_id: int):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Part not found")
        return dict(row)
    finally:
        conn.close()


# ==========================================================================
# IMAGES
# ==========================================================================

@app.get("/api/images/{part_id}")
async def get_part_image(part_id: int):
    """
    Serve the image for a part.
    Strategy 1: BLOB stored in part_images.image_data
    Strategy 2: File path stored in parts.image_path
    """
    conn = get_db_connection()
    try:
        # Try part_images table (BLOB storage from process_images.py)
        row = conn.execute("""
            SELECT image_data, image_type
            FROM part_images
            WHERE part_id = ?
            ORDER BY confidence DESC
            LIMIT 1
        """, (part_id,)).fetchone()

        if row and row["image_data"]:
            img_type = row["image_type"] or "png"
            return StreamingResponse(
                io.BytesIO(bytes(row["image_data"])),
                media_type=f"image/{img_type}",
                headers={"Content-Disposition": f"inline; filename=part_{part_id}.{img_type}"},
            )

        # Fallback: file path on parts table (set by extract_catalog.py)
        part = conn.execute(
            "SELECT image_path FROM parts WHERE id = ?", (part_id,)
        ).fetchone()

        if not part or not part["image_path"]:
            raise HTTPException(status_code=404, detail="No image for this part")

        resolved = resolve_image_path(part["image_path"])
        if not resolved:
            raise HTTPException(
                status_code=404,
                detail=f"Image file not found on disk: {part['image_path']}",
            )

        return StreamingResponse(
            open(resolved, "rb"),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=part_{part_id}.png"},
        )
    finally:
        conn.close()


@app.get("/images/{image_id}/data")
async def get_image_data(image_id: int):
    """Serve image by image row ID (used by legacy endpoints)."""
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT image_data, image_type
            FROM part_images
            WHERE id = ?
        """, (image_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Image not found")

        if row["image_data"]:
            img_type = row["image_type"] or "png"
            return StreamingResponse(
                io.BytesIO(bytes(row["image_data"])),
                media_type=f"image/{img_type}",
                headers={"Content-Disposition": f"filename=image_{image_id}.{img_type}"},
            )

        raise HTTPException(status_code=404, detail="Image data not available")
    finally:
        conn.close()


# ==========================================================================
# GUIDES
# ==========================================================================

@app.get("/guides", response_model=List[TechnicalGuide])
async def get_guides(active_only: bool = True):
    conn = get_db_connection()
    try:
        sql = """
            SELECT tg.*, COUNT(pg.part_id) AS part_count
            FROM technical_guides tg
            LEFT JOIN part_guides pg ON tg.id = pg.guide_id
        """
        if active_only:
            sql += " WHERE tg.is_active = 1"
        sql += " GROUP BY tg.id ORDER BY tg.display_name"
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


@app.get("/guides/{guide_id}")
async def get_guide(guide_id: int):
    conn = get_db_connection()
    try:
        guide = conn.execute(
            "SELECT * FROM technical_guides WHERE id = ?", (guide_id,)
        ).fetchone()
        if not guide:
            raise HTTPException(status_code=404, detail="Guide not found")

        parts = conn.execute("""
            SELECT p.*, pg.confidence_score
            FROM parts p
            JOIN part_guides pg ON p.id = pg.part_id
            WHERE pg.guide_id = ?
            ORDER BY pg.confidence_score DESC
        """, (guide_id,)).fetchall()

        return {
            "guide": dict(guide),
            "associated_parts": [dict(p) for p in parts],
            "part_count": len(parts),
        }
    finally:
        conn.close()


# ==========================================================================
# ASSOCIATIONS
# ==========================================================================

@app.post("/associations")
async def create_association(part_id: int, guide_id: int, confidence: float = 1.0):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO part_guides (part_id, guide_id, confidence_score)
            VALUES (?, ?, ?)
        """, (part_id, guide_id, confidence))
        conn.commit()
        return {"message": "Association created successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.delete("/associations")
async def delete_association(part_id: int, guide_id: int):
    conn = get_db_connection()
    try:
        conn.execute("""
            DELETE FROM part_guides WHERE part_id = ? AND guide_id = ?
        """, (part_id, guide_id))
        conn.commit()
        return {"message": "Association deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ==========================================================================
# ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)