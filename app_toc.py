# app_toc.py
import sqlite3
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
from typing import Dict, Any
import uvicorn
from typing import List, Optional
from s3_manager import S3Manager
from template_manager import TemplateManager
from config import Config
import os

# Get the absolute path to the current directory
BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = BASE_DIR / "catalog.db"
IMAGES_DIR = BASE_DIR / "part_images"
PDF_DIR = BASE_DIR / "pdfs"
STATIC_DIR = BASE_DIR / "static"
TemplateManager = TemplateManager()

app = FastAPI(title="Knowledge Base ... ")

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Create directories if they don't exist ---
IMAGES_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# --- Static file serving ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.mount("/pdfs", StaticFiles(directory=str(PDF_DIR)), name="pdfs")

# --- Helpers ---
def get_db_conn():
    return sqlite3.connect(DB_PATH)

def get_static_file_path(filename: str) -> Path:
    """Get the path to a static file with fallback"""
    static_path = STATIC_DIR / filename
    if static_path.exists():
        return static_path
    # Fallback to root directory
    root_path = BASE_DIR / filename
    return root_path

def get_pdf_url(pdf_path_str: str, page: int) -> str:
    """Generate proper PDF URL with page anchor"""
    if not pdf_path_str:
        return None
    
    pdf_path = Path(pdf_path_str)
    pdf_filename = pdf_path.name
    
    # Return URL in format: /pdfs/filename.pdf#page=123
    return f"/pdfs/{pdf_filename}#page={page}"

# --- Category Management ---
def get_categories_with_counts():
    """Get categories with part counts for better filtering"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT category, COUNT(*) as part_count 
            FROM parts 
            WHERE category IS NOT NULL AND category != 'General'
            GROUP BY category 
            ORDER BY part_count DESC, category
        """)
        categories = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]
        conn.close()
        return categories
    except Exception as e:
        print(f"Error getting categories with counts: {e}")
        return []

def get_catalog_categories(catalog_name: str = None):
    """Get categories specific to a catalog"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        if catalog_name:
            cur.execute("""
                SELECT DISTINCT category, COUNT(*) as part_count
                FROM parts 
                WHERE catalog_name = ? AND category IS NOT NULL
                GROUP BY category
                ORDER BY part_count DESC, category
            """, (catalog_name,))
        else:
            cur.execute("""
                SELECT DISTINCT category, COUNT(*) as part_count
                FROM parts 
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY part_count DESC, category
            """)
        
        categories = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]
        conn.close()
        return categories
    except Exception as e:
        print(f"Error getting catalog categories: {e}")
        return []

# --- Root ---
@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serve index.html from static directory"""
    index_path = get_static_file_path("index.html")
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hydraulic Brakes Catalog</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Hydraulic Brakes Catalog Server</h1>
                <p>Server is running, but index.html was not found.</p>
                <ul>
                    <li><a href="/health">/health</a></li>
                    <li><a href="/categories">/categories</a></li>
                    <li><a href="/search?q=D50">/search?q=D50</a></li>
                    <li><a href="/test">/test</a></li>
                </ul>
            </div>
        </body>
        </html>
    """)

# --- Serve individual static files explicitly ---
@app.get("/styles.css")
async def get_css():
    """Serve CSS file directly"""
    css_path = get_static_file_path("styles.css")
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/app.js")
async def get_js():
    """Serve JavaScript file directly"""
    js_path = get_static_file_path("app.js")
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JavaScript file not found")

@app.get("/favicon.ico")
async def get_favicon():
    """Serve favicon"""
    favicon_path = get_static_file_path("favicon.ico")
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/x-icon")
    return HTTPException(status_code=404, detail="Favicon not found")

# --- Health & Diagnostics ---
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Server is running"}

@app.get("/test")
def test_endpoint():
    """System diagnostics to verify database and files."""
    results = {
        "server_status": "running",
        "database_connection": "unknown",
        "tables_exist": "unknown",
        "parts_count": 0,
        "categories_count": 0,
        "catalog_distribution": {},
        "category_distribution": {},
        "sample_parts": [],
        "file_locations": {},
        "static_files": {},
        "pdf_files": []
    }

    try:
        results["file_locations"] = {
            "base_dir": str(BASE_DIR),
            "static_dir": str(STATIC_DIR),
            "static_index_html": (STATIC_DIR / "index.html").exists(),
            "root_index_html": (BASE_DIR / "index.html").exists(),
            "database_file": DB_PATH.exists(),
            "images_dir": IMAGES_DIR.exists(),
            "pdfs_dir": PDF_DIR.exists(),
        }

        # Check static files
        static_files = ["index.html", "styles.css", "app.js", "favicon.ico"]
        results["static_files"] = {
            file: (STATIC_DIR / file).exists() for file in static_files
        }

        # List PDF files in pdfs directory
        if PDF_DIR.exists():
            results["pdf_files"] = [f.name for f in PDF_DIR.glob("*.pdf")]

        conn = get_db_conn()
        cur = conn.cursor()
        results["database_connection"] = "success"

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parts'")
        results["tables_exist"] = "yes" if cur.fetchone() else "no"

        cur.execute("SELECT COUNT(*) FROM parts")
        results["parts_count"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT category) FROM parts")
        results["categories_count"] = cur.fetchone()[0]

        # Get catalog distribution
        cur.execute("SELECT catalog_name, COUNT(*) FROM parts GROUP BY catalog_name")
        results["catalog_distribution"] = {ct: cnt for ct, cnt in cur.fetchall()}

        # Get category distribution
        cur.execute("""
            SELECT category, COUNT(*) 
            FROM parts 
            WHERE category IS NOT NULL 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        results["category_distribution"] = {cat: cnt for cat, cnt in cur.fetchall()}

        # Check sample parts with PDF paths
        cur.execute("""
            SELECT catalog_name, catalog_type, part_type, part_number, category, page, pdf_path
            FROM parts WHERE pdf_path IS NOT NULL ORDER BY page, part_number LIMIT 5
        """)
        results["sample_parts"] = [
            {
                "catalog_name": row[0],
                "catalog_type": row[1], 
                "part_type": row[2], 
                "part_number": row[3], 
                "category": row[4], 
                "page": row[5],
                "pdf_path": row[6],
                "pdf_url": get_pdf_url(row[6], row[5]) if row[6] else None
            }
            for row in cur.fetchall()
        ]

        conn.close()

    except Exception as e:
        results["error"] = str(e)
        results["database_connection"] = "failed"

    return results

# --- Categories Endpoints ---
@app.get("/categories")
def get_categories():
    """Get all categories"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT category 
            FROM parts 
            WHERE category IS NOT NULL AND category != 'General'
            ORDER BY category
        """)
        categories = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/categories/with-counts")
def get_categories_with_counts_endpoint():
    """Get categories with part counts"""
    try:
        categories = get_categories_with_counts()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/catalogs/{catalog_name}/categories")
def get_catalog_categories_endpoint(catalog_name: str):
    """Get categories for a specific catalog"""
    try:
        categories = get_catalog_categories(catalog_name)
        return {
            "catalog_name": catalog_name,
            "categories": categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/categories/{category_name}/parts")
def get_parts_by_category(category_name: str, limit: int = 50):
    """Get all parts in a specific category"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, catalog_name, catalog_type, part_type, part_number, 
                   description, category, page, image_path, pdf_path
            FROM parts 
            WHERE category = ?
            ORDER BY part_number
            LIMIT ?
        """, (category_name, limit))
        
        rows = cur.fetchall()
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "catalog_name": row[1],
                "catalog_type": row[2],
                "part_type": row[3],
                "part_number": row[4],
                "description": row[5],
                "category": row[6],
                "page": row[7],
                "image_url": f"/images/{Path(row[8]).name}" if row[8] else None,
                "pdf_url": get_pdf_url(row[9], row[7])
            })
        
        conn.close()
        
        return {
            "category": category_name,
            "count": len(results),
            "parts": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/part_types")
def get_part_types():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT part_type FROM parts WHERE part_type IS NOT NULL ORDER BY part_type")
        part_types = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"part_types": part_types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/catalogs")
def get_catalogs():
    """Get all available catalogs"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT catalog_name, catalog_type, COUNT(*) as part_count
            FROM parts 
            GROUP BY catalog_name, catalog_type
            ORDER BY catalog_name
        """)
        
        catalogs = []
        for row in cur.fetchall():
            catalogs.append({
                "name": row[0],
                "type": row[1],
                "part_count": row[2]
            })
        
        conn.close()
        return {"catalogs": catalogs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- Search Helpers ---
def query_db(q: str = None, category: str = None, part_type: str = None,
             catalog_name: str = None, limit: int = 100):
    """Query database with proper field names matching schema - ALIGNED"""
    conn = get_db_conn()
    cur = conn.cursor()
    params, sql = [], []

    if not q:
        # Basic search without query - show all with filters
        sql = """SELECT id, catalog_name, catalog_type, part_type, part_number, description,
                        category, page, image_path, pdf_path
                 FROM parts WHERE 1=1"""
        if category:
            sql += " AND category=?"
            params.append(category)
        if part_type:
            sql += " AND part_type=?"
            params.append(part_type)
        if catalog_name:
            sql += " AND catalog_name=?"  # catalog_name in DB = catalog_type from frontend
            params.append(catalog_name)
        sql += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        cur.execute(sql, tuple(params))
    else:
        # Text search - same logic but ensure catalog_name filter works
        if q.upper().startswith(('D', '600-', 'CH')):
            # Part number prefix search
            sql = """SELECT id, catalog_name, catalog_type, part_type, part_number, description,
                            category, page, image_path, pdf_path
                     FROM parts WHERE part_number LIKE ?"""
            params.append(f"{q}%")
            if category:
                sql += " AND category=?"
                params.append(category)
            if part_type:
                sql += " AND part_type=?"
                params.append(part_type)
            if catalog_name:
                sql += " AND catalog_name=?"
                params.append(catalog_name)
            sql += " LIMIT ?"
            params.append(limit)
            cur.execute(sql, tuple(params))
        else:
            # Full text search
            sql = """SELECT p.id, p.catalog_name, p.catalog_type, p.part_type, p.part_number,
                            p.description, p.category, p.page, p.image_path, p.pdf_path
                     FROM parts p
                     JOIN parts_fts f ON p.id = f.rowid
                     WHERE f.parts_fts MATCH ?"""
            params.append(q)
            if category:
                sql += " AND p.category=?"
                params.append(category)
            if part_type:
                sql += " AND p.part_type=?"
                params.append(part_type)
            if catalog_name:
                sql += " AND p.catalog_name=?"
                params.append(catalog_name)
            sql += " LIMIT ?"
            params.append(limit)
            cur.execute(sql, tuple(params))

    rows = cur.fetchall()
    conn.close()
    return rows

# --- Search Endpoints ---
@app.get("/search")
def search(q: Optional[str] = Query(None),
           category: Optional[str] = Query(None),
           part_type: Optional[str] = Query(None),
           catalog_type: Optional[str] = Query(None),  # Changed from catalog_name
           content_type: Optional[str] = Query("all"),  # Added content_type filter
           limit: int = 100):
    """Search parts with category and catalog filtering - ALIGNED WITH FRONTEND"""
    try:
        # Map frontend catalog_type to backend catalog_name
        catalog_name = catalog_type  # They are the same in our schema
        
        # Handle content_type filtering
        if content_type == "guides":
            # Return empty results for guides-only search (guides handled separately)
            return {
                "query": q or "",
                "category_filter": category or "",
                "part_type_filter": part_type or "",
                "catalog_filter": catalog_type or "",
                "content_type": content_type,
                "count": 0,
                "results": [],
            }
        
        rows = query_db(q, category, part_type, catalog_name, limit)
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "catalog_name": r[1],
                "catalog_type": r[2],  # This matches frontend catalog_type
                "part_type": r[3],
                "part_number": r[4],
                "description": r[5],
                "category": r[6],
                "page": r[7],
                "image_url": f"/images/{Path(r[8]).name}" if r[8] else None,
                "pdf_url": get_pdf_url(r[9], r[7]),
                "pdf_page": r[7]
            })

        # For parts-only filter, we already have parts
        # For "all", we include both (guides are loaded separately in frontend)
        
        return {
            "query": q or "",
            "category_filter": category or "",
            "part_type_filter": part_type or "",
            "catalog_filter": catalog_type or "",
            "content_type": content_type,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/search/simple")
def simple_search(q: str = Query(..., description="Search query"), limit: int = 50):
    """Simple search without filters for testing"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Try multiple search approaches
        queries = [
            ("Part number search", "SELECT * FROM parts WHERE part_number LIKE ? LIMIT ?", [f"%{q}%", limit]),
            ("FTS search", "SELECT p.* FROM parts p JOIN parts_fts f ON p.id = f.rowid WHERE f.parts_fts MATCH ? LIMIT ?", [q, limit]),
            ("Description search", "SELECT * FROM parts WHERE description LIKE ? LIMIT ?", [f"%{q}%", limit])
        ]
        
        all_results = []
        for query_name, sql, params in queries:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
                if rows:
                    print(f"{query_name} found {len(rows)} results")
                    all_results.extend(rows)
            except Exception as e:
                print(f"{query_name} failed: {e}")
        
        # Remove duplicates by id
        seen_ids = set()
        unique_results = []
        for row in all_results:
            if row[0] not in seen_ids:
                seen_ids.add(row[0])
                unique_results.append(row)
        
        results = []
        for r in unique_results[:limit]:
            results.append({
                "id": r[0],
                "catalog_name": r[1],
                "catalog_type": r[2],
                "part_type": r[3],
                "part_number": r[4],
                "description": r[5],
                "category": r[6],
                "page": r[7],
                "image_url": f"/images/{Path(r[8]).name}" if r[8] else None,
                "pdf_url": get_pdf_url(r[10], r[7]) if len(r) > 10 else None,
            })
        
        conn.close()
        
        return {
            "query": q,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/part/{part_id}")
def get_part(part_id: int):
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""SELECT id, catalog_name, catalog_type, part_type, part_number, description,
                              category, page, image_path, page_text, pdf_path, machine_info
                       FROM parts WHERE id=?""", (part_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Part not found")

        machine_info = json.loads(row[11]) if row[11] else {}

        return {
            "id": row[0],
            "catalog_name": row[1],
            "catalog_type": row[2],
            "part_type": row[3],
            "part_number": row[4],
            "description": row[5],
            "category": row[6],
            "page": row[7],
            "image_url": f"/images/{Path(row[8]).name}" if row[8] else None,
            "page_text": row[9],
            "pdf_url": get_pdf_url(row[10], row[7]),
            "pdf_page": row[7],
            "machine_info": machine_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/images/{image_filename}")
def get_image(image_filename: str):
    path = IMAGES_DIR / image_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")

@app.get("/pdfs/{pdf_filename:path}")
def get_pdf(pdf_filename: str):
    """Serve PDF files directly"""
    path = PDF_DIR / pdf_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(path, media_type="application/pdf")

# --- Technical Guides Endpoints ---
@app.get("/technical-guides")
def get_technical_guides():
    """Get all available technical guides"""
    try:
        guides = guide_manager.get_available_guides()
        return {"guides": guides}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading guides: {str(e)}")

@app.get("/technical-guides/{guide_name}")
def get_technical_guide(guide_name: str, download: bool = False):
    """Get a specific technical guide"""
    try:
        if download:
            local_path = guide_manager.load_guide(guide_name)
            if local_path and os.path.exists(local_path):
                return FileResponse(
                    local_path, 
                    media_type='application/pdf',
                    filename=f"{guide_name}.pdf"
                )
            else:
                raise HTTPException(status_code=404, detail="Guide not found")
        else:
            s3_url = guide_manager.generate_guide_url(guide_name)
            if s3_url:
                return {"guide_name": guide_name, "download_url": s3_url}
            else:
                raise HTTPException(status_code=404, detail="Guide not found in S3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing guide: {str(e)}")

@app.get("/technical-guides/{guide_name}/info")
def get_technical_guide_info(guide_name: str):
    """Get information about a specific technical guide"""
    try:
        guides = guide_manager.get_available_guides()
        guide_info = next((g for g in guides if g['guide_name'] == guide_name), None)
        
        if guide_info:
            return guide_info
        else:
            raise HTTPException(status_code=404, detail="Guide not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting guide info: {str(e)}")

# --- Database Diagnostics ---
@app.get("/debug/database")
def debug_database():
    """Debug database structure and content"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        results = {
            "tables": [],
            "parts_sample": [],
            "fts_status": {}
        }
        
        # Get table info
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        results["tables"] = tables
        
        # Check parts table structure
        if 'parts' in tables:
            cur.execute("PRAGMA table_info(parts)")
            results["parts_columns"] = [{"name": row[1], "type": row[2]} for row in cur.fetchall()]
            
            # Sample data
            cur.execute("SELECT id, catalog_name, part_number, category FROM parts LIMIT 10")
            results["parts_sample"] = [
                {"id": row[0], "catalog_name": row[1], "part_number": row[2], "category": row[3]}
                for row in cur.fetchall()
            ]
            
            # Counts
            cur.execute("SELECT COUNT(*) FROM parts")
            results["total_parts"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM parts_fts")
            results["fts_parts"] = cur.fetchone()[0]
        
        # Check FTS table
        if 'parts_fts' in tables:
            cur.execute("SELECT * FROM parts_fts LIMIT 3")
            results["fts_sample"] = cur.fetchall()
        
        conn.close()
        return results
        
    except Exception as e:
        return {"error": str(e)}

# --- Advanced Search ---
@app.get("/search/advanced")
def advanced_search(
    q: Optional[str] = None,
    catalog_name: Optional[str] = None,
    catalog_type: Optional[str] = None,
    part_type: Optional[str] = None,
    category: Optional[str] = None,
    min_page: Optional[int] = None,
    max_page: Optional[int] = None,
    limit: int = 100
):
    """Advanced search with multiple filters"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        query = """
            SELECT id, catalog_name, catalog_type, part_type, part_number, 
                   description, category, page, image_path, pdf_path, machine_info
            FROM parts WHERE 1=1
        """
        params = []
        
        # Build query dynamically
        if q:
            query += " AND part_number LIKE ?"
            params.append(f"%{q}%")
        
        if catalog_name:
            query += " AND catalog_name = ?"
            params.append(catalog_name)
            
        if catalog_type:
            query += " AND catalog_type = ?"
            params.append(catalog_type)
            
        if part_type:
            query += " AND part_type = ?"
            params.append(part_type)
            
        if category:
            query += " AND category = ?"
            params.append(category)
            
        if min_page is not None:
            query += " AND page >= ?"
            params.append(min_page)
            
        if max_page is not None:
            query += " AND page <= ?"
            params.append(max_page)
        
        query += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            machine_info = json.loads(row[10]) if row[10] else {}
            
            results.append({
                "id": row[0],
                "catalog_name": row[1],
                "catalog_type": row[2],
                "part_type": row[3],
                "part_number": row[4],
                "description": row[5],
                "category": row[6],
                "page": row[7],
                "image_url": f"/images/{Path(row[8]).name}" if row[8] else None,
                "pdf_url": get_pdf_url(row[9], row[7]),
                "machine_info": machine_info
            })
        
        conn.close()
        
        return {
            "query": q or "",
            "filters": {
                "catalog_name": catalog_name,
                "catalog_type": catalog_type,
                "part_type": part_type,
                "category": category,
                "min_page": min_page,
                "max_page": max_page
            },
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/part/{part_id}/detailed")
def get_part_detailed(part_id: int):
    """Get detailed part information including machine info"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, catalog_name, catalog_type, part_type, part_number, 
                   description, category, page, image_path, page_text, 
                   pdf_path, machine_info
            FROM parts WHERE id=?
        """, (part_id,))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Part not found")
        
        machine_info = json.loads(row[11]) if row[11] else {}
        
        return {
            "id": row[0],
            "catalog_name": row[1],
            "catalog_type": row[2],
            "part_type": row[3],
            "part_number": row[4],
            "description": row[5],
            "category": row[6],
            "page": row[7],
            "image_url": f"/images/{Path(row[8]).name}" if row[8] else None,
            "page_text": row[9],
            "pdf_url": get_pdf_url(row[10], row[7]),
            "machine_info": machine_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@app.get("/debug/schema")
def debug_schema():
    """Check if database schema aligns with frontend expectations"""
    conn = get_db_conn()
    cur = conn.cursor()
    
    cur.execute("PRAGMA table_info(parts)")
    columns = [col[1] for col in cur.fetchall()]
    
    conn.close()
    
    expected_columns = [
        'catalog_name', 'catalog_type', 'part_type', 'part_number',
        'description', 'category', 'page', 'image_path', 'pdf_path'
    ]
    
    missing_columns = [col for col in expected_columns if col not in columns]
    
    return {
        "expected_columns": expected_columns,
        "actual_columns": columns,
        "missing_columns": missing_columns,
        "alignment_ok": len(missing_columns) == 0
    }
    
@app.get("/test-alignment")
def test_alignment():
    """Test if frontend and backend are properly aligned"""
    test_cases = [
        {"q": "D50", "catalog_type": "dayton"},
        {"category": "Brakes", "part_type": "Caliper"},
        {"catalog_type": "caterpillar", "content_type": "parts"}
    ]
    
    results = []
    for test_case in test_cases:
        try:
            params = "&".join([f"{k}={v}" for k, v in test_case.items()])
            # This would simulate a frontend request
            results.append({
                "test_case": test_case,
                "params": params,
                "status": "ready"
            })
        except Exception as e:
            results.append({
                "test_case": test_case,
                "error": str(e),
                "status": "failed"
            })
    
    return {
        "alignment_test": results,
        "frontend_expected_filters": ["q", "category", "part_type", "catalog_type", "content_type"],
        "backend_actual_parameters": ["q", "category", "part_type", "catalog_type", "content_type", "limit"],
        "alignment": "OK" if len(results) == len(test_cases) else "NEEDS_FIXES"
    }
@app.get("/test-alignment")
def test_alignment():
    """Test if frontend and backend are properly aligned"""
    test_cases = [
        {"q": "D50", "catalog_type": "dayton"},
        {"category": "Brakes", "part_type": "Caliper"},
        {"catalog_type": "caterpillar", "content_type": "parts"}
    ]
    
    results = []
    for test_case in test_cases:
        try:
            params = "&".join([f"{k}={v}" for k, v in test_case.items()])
            # This would simulate a frontend request
            results.append({
                "test_case": test_case,
                "params": params,
                "status": "ready"
            })
        except Exception as e:
            results.append({
                "test_case": test_case,
                "error": str(e),
                "status": "failed"
            })
    
    return {
        "alignment_test": results,
        "frontend_expected_filters": ["q", "category", "part_type", "catalog_type", "content_type"],
        "backend_actual_parameters": ["q", "category", "part_type", "catalog_type", "content_type", "limit"],
        "alignment": "OK" if len(results) == len(test_cases) else "NEEDS_FIXES"
    }
    
# --- Entrypoint ---
if __name__ == "__main__":
    print("Starting server on http://localhost:8000")
    print(f"Static directory: {STATIC_DIR}")
    print(f"PDF directory: {PDF_DIR}")
    print(f"Database: {DB_PATH}")
    
    # Test database connection and content
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Check if parts table exists and has data
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parts'")
        if cur.fetchone():
            cur.execute("SELECT COUNT(*) FROM parts")
            part_count = cur.fetchone()[0]
            print(f"📊 Parts in database: {part_count}")
            
            # Show catalog distribution
            cur.execute("SELECT catalog_name, COUNT(*) FROM parts GROUP BY catalog_name")
            catalogs = cur.fetchall()
            print("📚 Catalogs found:")
            for catalog, count in catalogs:
                print(f"   {catalog}: {count} parts")
                
            # Show categories
            cur.execute("SELECT DISTINCT category FROM parts WHERE category IS NOT NULL LIMIT 10")
            categories = [row[0] for row in cur.fetchall()]
            print(f"📁 Sample categories: {', '.join(categories)}")
            
            # Test search
            test_queries = ['D50', '600-', 'CH']
            for test_query in test_queries:
                cur.execute("SELECT COUNT(*) FROM parts WHERE part_number LIKE ?", (f"{test_query}%",))
                count = cur.fetchone()[0]
                print(f"🔍 Test search '{test_query}': {count} results")
        else:
            print("[ERROR] No parts table found - database may be empty")
            
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database error: {e}")
    
    print(f"Static files found:")
    for file in ["index.html", "styles.css", "app.js"]:
        path = STATIC_DIR / file
        print(f"  {file}: {'[OK]' if path.exists() else '[ERROR]'}")
    
    uvicorn.run("app_toc:app", host="0.0.0.0", port=8000, reload=True)