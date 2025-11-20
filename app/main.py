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

app = FastAPI(title="Knowledge Base", version="1.0.0")

# Mount static files directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Serve the main page
@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Serve the static HTML file directly
    html_file_path = Path("app/static/index.html")
    if html_file_path.exists():
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    else:
        # Fallback: return a simple HTML page
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Parts Catalog</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .error { color: red; }
            </style>
        </head>
        <body>
            <h1>Parts Catalog Application</h1>
            <p class="error">Warning: index.html not found in static directory.</p>
            <p>Please ensure your frontend files are in the correct location.</p>
            <p><a href="/docs">API Documentation</a></p>
        </body>
        </html>
        """)

# Database connection
def get_db_connection():
    db_path = Path("C:/Users/kpecco/Desktop/codes/TESTING/app/data/catalog.db")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

# Pydantic Models
class PartBase(BaseModel):
    id: int
    catalog_name: str
    part_number: str
    description: Optional[str]
    category: Optional[str]
    page: Optional[int]

class PartDetail(PartBase):
    catalog_type: Optional[str]
    part_type: Optional[str]
    image_path: Optional[str]
    machine_info: Optional[str]
    specifications: Optional[str]
    oe_numbers: Optional[str]
    applications: Optional[str]
    features: Optional[str]
    created_at: str

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
    description: Optional[str]
    category: Optional[str]
    pdf_path: Optional[str]
    is_active: bool
    part_count: int

class SearchResponse(BaseModel):
    parts: List[PartBase]
    total_count: int
    page: int
    page_size: int

# NEW: Enhanced search endpoint that matches frontend requirements
@app.get("/api/search")
async def api_search_parts(
    q: str = Query("", min_length=0),
    category: str = Query(""),
    part_type: str = Query(""),
    catalog_type: str = Query(""),
    limit: int = Query(50, ge=1, le=200)
    
):
    conn = get_db_connection()
    try:
        where_conditions = []
        params = []
        
        # Handle search query
        if q and q.strip():
            # Simple LIKE search for part number and description
            where_conditions.append("(p.part_number LIKE ? OR p.description LIKE ?)")
            search_term = f"%{q}%"
            params.extend([search_term, search_term])
        
        # Handle filters
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
        
        # Build query
        query = f"""
            SELECT p.*,
                   (SELECT COUNT(*) FROM part_images pi WHERE pi.part_id = p.id) as image_count
            FROM parts p
            {where_clause}
            ORDER BY p.part_number
            LIMIT ?
        """
        params.append(limit)
        
        parts = conn.execute(query, params).fetchall()
        
        return {
            "query": q,
            "results": [dict(part) for part in parts],
            "count": len(parts)
        }
    finally:
        conn.close()

# NEW: API endpoint for categories analytics
@app.get("/api/analytics/categories")
async def api_get_categories():
    conn = get_db_connection()
    try:
        categories = conn.execute("""
            SELECT 
                category,
                COUNT(*) as part_count
            FROM parts
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY part_count DESC
        """).fetchall()
        
        return [{"category": cat['category'], "part_count": cat['part_count']} for cat in categories]
    finally:
        conn.close()

# NEW: API endpoint for catalogs analytics
@app.get("/api/analytics/catalogs")
async def api_get_catalogs():
    conn = get_db_connection()
    try:
        catalogs = conn.execute("""
            SELECT 
                catalog_name,
                COUNT(*) as part_count
            FROM parts
            WHERE catalog_name IS NOT NULL AND catalog_name != ''
            GROUP BY catalog_name
            ORDER BY part_count DESC
        """).fetchall()
        
        return [{"catalog_name": cat['catalog_name'], "part_count": cat['part_count']} for cat in catalogs]
    finally:
        conn.close()

# Parts Endpoints
@app.get("/parts", response_model=SearchResponse)
async def get_parts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    catalog: Optional[str] = None,
    category: Optional[str] = None
):
    conn = get_db_connection()
    try:
        offset = (page - 1) * page_size
        
        where_conditions = []
        params = []
        
        if catalog:
            where_conditions.append("catalog_name = ?")
            params.append(catalog)
        
        if category:
            where_conditions.append("category = ?")
            params.append(category)
        
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM parts {where_clause}"
        total_count = conn.execute(count_query, params).fetchone()[0]
        
        # Get paginated results
        query = f"""
            SELECT p.*, 
                   (SELECT COUNT(*) FROM part_images pi WHERE pi.part_id = p.id) as image_count,
                   (SELECT COUNT(*) FROM part_guides pg WHERE pg.part_id = p.id) as guide_count
            FROM parts p
            {where_clause}
            ORDER BY p.id
            LIMIT ? OFFSET ?
        """
        params.extend([page_size, offset])
        
        parts = conn.execute(query, params).fetchall()
        
        return SearchResponse(
            parts=[dict(part) for part in parts],
            total_count=total_count,
            page=page,
            page_size=page_size
        )
    finally:
        conn.close()

@app.get("/parts/{part_id}", response_model=PartDetail)
async def get_part(part_id: int):
    conn = get_db_connection()
    try:
        part = conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        return dict(part)
    finally:
        conn.close()

# NEW: API endpoint for part details (used by frontend)
@app.get("/api/parts/{part_id}")
async def api_get_part(part_id: int):
    conn = get_db_connection()
    try:
        part = conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        return dict(part)
    finally:
        conn.close()

@app.get("/parts/search/{part_number}")
async def search_part_by_number(part_number: str):
    conn = get_db_connection()
    try:
        parts = conn.execute("""
            SELECT p.*, 
                   GROUP_CONCAT(DISTINCT pi.image_filename) as images,
                   GROUP_CONCAT(DISTINCT tg.display_name) as guides
            FROM parts p
            LEFT JOIN part_images pi ON p.id = pi.part_id
            LEFT JOIN part_guides pg ON p.id = pg.part_id
            LEFT JOIN technical_guides tg ON pg.guide_id = tg.id
            WHERE p.part_number = ?
            GROUP BY p.id
        """, (part_number,)).fetchall()
        
        if not parts:
            raise HTTPException(status_code=404, detail="Part not found")
        
        return [dict(part) for part in parts]
    finally:
        conn.close()

@app.get("/parts/{part_id}/images")
async def get_part_images(part_id: int):
    conn = get_db_connection()
    try:
        images = conn.execute("""
            SELECT * FROM part_images 
            WHERE part_id = ? 
            ORDER BY confidence DESC, created_at DESC
        """, (part_id,)).fetchall()
        
        return [dict(image) for image in images]
    finally:
        conn.close()

@app.get("/images/{image_id}/data")
async def get_image_data(image_id: int):
    conn = get_db_connection()
    try:
        image = conn.execute("""
            SELECT image_data, image_type 
            FROM part_images 
            WHERE id = ?
        """, (image_id,)).fetchone()
        
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")
        
        return StreamingResponse(
            io.BytesIO(image['image_data']),
            media_type=f"image/{image['image_type']}",
            headers={"Content-Disposition": f"filename=image_{image_id}.{image['image_type']}"}
        )
    finally:
        conn.close()

# Guides Endpoints
@app.get("/guides", response_model=List[TechnicalGuide])
async def get_guides(active_only: bool = True):
    conn = get_db_connection()
    try:
        query = """
            SELECT tg.*,
                   COUNT(pg.part_id) as part_count
            FROM technical_guides tg
            LEFT JOIN part_guides pg ON tg.id = pg.guide_id
        """
        
        if active_only:
            query += " WHERE tg.is_active = 1"
            
        query += " GROUP BY tg.id ORDER BY tg.display_name"
        
        guides = conn.execute(query).fetchall()
        return [dict(guide) for guide in guides]
    finally:
        conn.close()

@app.get("/guides/{guide_id}")
async def get_guide(guide_id: int):
    conn = get_db_connection()
    try:
        guide = conn.execute("SELECT * FROM technical_guides WHERE id = ?", (guide_id,)).fetchone()
        if not guide:
            raise HTTPException(status_code=404, detail="Guide not found")
        
        # Get associated parts
        parts = conn.execute("""
            SELECT p.*, pg.confidence_score
            FROM parts p
            JOIN part_guides pg ON p.id = pg.part_id
            WHERE pg.guide_id = ?
            ORDER BY pg.confidence_score DESC
        """, (guide_id,)).fetchall()
        
        return {
            "guide": dict(guide),
            "associated_parts": [dict(part) for part in parts],
            "part_count": len(parts)
        }
    finally:
        conn.close()

@app.get("/parts/{part_id}/guides")
async def get_part_guides(part_id: int):
    conn = get_db_connection()
    try:
        guides = conn.execute("""
            SELECT tg.*, pg.confidence_score
            FROM technical_guides tg
            JOIN part_guides pg ON tg.id = pg.guide_id
            WHERE pg.part_id = ?
            ORDER BY pg.confidence_score DESC
        """, (part_id,)).fetchall()
        
        return [dict(guide) for guide in guides]
    finally:
        conn.close()

# Search Endpoints
@app.get("/search")
async def search_parts(
    q: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=200)
):
    conn = get_db_connection()
    try:
        # FTS search
        parts = conn.execute("""
            SELECT p.*, 
                   snippet(parts_fts, 2, '<b>', '</b>', '...', 64) as snippet
               FROM parts_fts
               JOIN parts p ON p.id = parts_fts.rowid
               WHERE parts_fts MATCH ?
               ORDER BY rank
               LIMIT ?
        """, (f'"{q}"*', limit)).fetchall()
        
        return {
            "query": q,
            "results": [dict(part) for part in parts],
            "count": len(parts)
        }
    finally:
        conn.close()

# Analytics Endpoints
@app.get("/analytics/catalogs")
async def get_catalog_analytics():
    conn = get_db_connection()
    try:
        catalogs = conn.execute("""
            SELECT 
                catalog_name,
                COUNT(*) as part_count,
                COUNT(DISTINCT part_number) as unique_part_numbers,
                COUNT(DISTINCT category) as category_count,
                ROUND(COUNT(image_path) * 100.0 / COUNT(*), 2) as image_coverage_percent
            FROM parts
            GROUP BY catalog_name
            ORDER BY part_count DESC
        """).fetchall()
        
        return [dict(catalog) for catalog in catalogs]
    finally:
        conn.close()

@app.get("/analytics/categories")
async def get_category_analytics():
    conn = get_db_connection()
    try:
        categories = conn.execute("""
            SELECT 
                category,
                COUNT(*) as part_count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM parts), 2) as percentage
            FROM parts
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY part_count DESC
        """).fetchall()
        
        return [dict(category) for category in categories]
    finally:
        conn.close()

@app.get("/analytics/dashboard")
async def get_dashboard_stats():
    conn = get_db_connection()
    try:
        stats = conn.execute("""
            SELECT 
                (SELECT COUNT(*) FROM parts) as total_parts,
                (SELECT COUNT(*) FROM part_images) as total_images,
                (SELECT COUNT(*) FROM technical_guides) as total_guides,
                (SELECT COUNT(*) FROM part_guides) as total_associations,
                (SELECT COUNT(*) FROM parts WHERE image_path IS NOT NULL) as parts_with_image_reference,
                (SELECT COUNT(DISTINCT part_id) FROM part_images) as unique_parts_with_images
        """).fetchone()
        
        return dict(stats)
    finally:
        conn.close()

# Association Management
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
            DELETE FROM part_guides 
            WHERE part_id = ? AND guide_id = ?
        """, (part_id, guide_id))
        conn.commit()
        
        return {"message": "Association deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.get("/api/config")
async def get_config():
    return {
        "maxDescriptionLength": 120,
        "maxApplicationsDisplay": 2,
        "searchDebounceMs": 300,
        "enableTechnicalGuides": True,
        "maxSearchResults": 50
    }

@app.get("/api/parts/types")
async def get_part_types():
    conn = get_db_connection()
    try:
        part_types = conn.execute("""
            SELECT DISTINCT part_type FROM parts 
            WHERE part_type IS NOT NULL AND part_type != ''
            ORDER BY part_type
        """).fetchall()
        return {"part_types": [pt[0] for pt in part_types]}
    finally:
        conn.close()

@app.get("/api/images/{part_id}")
async def get_part_image(part_id: int):
    conn = get_db_connection()
    try:
        image = conn.execute("""
            SELECT image_data, image_type 
            FROM part_images 
            WHERE part_id = ? 
            ORDER BY confidence DESC 
            LIMIT 1
        """, (part_id,)).fetchone()
        
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")
        
        return StreamingResponse(
            io.BytesIO(image['image_data']),
            media_type=f"image/{image['image_type']}",
            headers={"Content-Disposition": f"inline; filename=part_{part_id}.{image['image_type']}"}
        )
    finally:
        conn.close()

# NEW: API endpoint for part guides (used by frontend)
@app.get("/api/parts/{part_id}/guides")
async def api_get_part_guides(part_id: int):
    conn = get_db_connection()
    try:
        guides = conn.execute("""
            SELECT tg.*, pg.confidence_score
            FROM technical_guides tg
            JOIN part_guides pg ON tg.id = pg.guide_id
            WHERE pg.part_id = ?
            ORDER BY pg.confidence_score DESC
        """, (part_id,)).fetchall()
        
        return [dict(guide) for guide in guides]
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)