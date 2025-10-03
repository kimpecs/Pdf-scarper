# app_toc.py
import sqlite3
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn
from typing import List, Optional

# Get the absolute path to the current directory
BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = BASE_DIR / "catalog.db"
IMAGES_DIR = BASE_DIR / "page_images"
PDF_DIR = BASE_DIR / "pdfs"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Hydraulic Brakes Catalog Search API")

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
    # Return a simple favicon to avoid 404 errors
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

        cur.execute("SELECT catalog_type, COUNT(*) FROM parts GROUP BY catalog_type")
        results["catalog_distribution"] = {ct: cnt for ct, cnt in cur.fetchall()}

        # Check sample parts with PDF paths
        cur.execute("""
            SELECT catalog_type, part_type, part_number, category, page, pdf_path
            FROM parts WHERE pdf_path IS NOT NULL ORDER BY page, part_number LIMIT 5
        """)
        results["sample_parts"] = [
            {
                "catalog": row[0], 
                "type": row[1], 
                "number": row[2], 
                "category": row[3], 
                "page": row[4],
                "pdf_path": row[5],
                "pdf_url": get_pdf_url(row[5], row[4]) if row[5] else None
            }
            for row in cur.fetchall()
        ]

        conn.close()

    except Exception as e:
        results["error"] = str(e)
        results["database_connection"] = "failed"

    return results

# --- Categories / Part Types ---
@app.get("/categories")
def get_categories():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM parts WHERE category IS NOT NULL ORDER BY category")
        categories = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"categories": categories}
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
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT catalog_type FROM parts ORDER BY catalog_type")
        catalogs = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"catalogs": catalogs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- Search Helpers ---
def query_db(q: str = None, category: str = None, part_type: str = None,
             catalog_type: str = None, limit: int = 100):
    conn = get_db_conn()
    cur = conn.cursor()
    params, sql = [], ""

    if not q:
        sql = """SELECT id, catalog_type, part_type, part_number, description,
                        category, page, image_path, pdf_path
                 FROM parts WHERE 1=1"""
        if category:
            sql += " AND category=?"
            params.append(category)
        if part_type:
            sql += " AND part_type=?"
            params.append(part_type)
        if catalog_type:
            sql += " AND catalog_type=?"
            params.append(catalog_type)
        sql += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        cur.execute(sql, tuple(params))
    else:
        if q.upper().startswith(('D', '600-', 'CH')):
            sql = """SELECT id, catalog_type, part_type, part_number, description,
                            category, page, image_path, pdf_path
                     FROM parts WHERE part_number LIKE ?"""
            params.append(f"{q}%")
            if category:
                sql += " AND category=?"
                params.append(category)
            if part_type:
                sql += " AND part_type=?"
                params.append(part_type)
            if catalog_type:
                sql += " AND catalog_type=?"
                params.append(catalog_type)
            sql += " LIMIT ?"
            params.append(limit)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            conn.close()
            return rows

        sql = """SELECT p.id, p.catalog_type, p.part_type, p.part_number,
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
        if catalog_type:
            sql += " AND p.catalog_type=?"
            params.append(catalog_type)
        sql += " LIMIT ?"
        params.append(limit)
        cur.execute(sql, tuple(params))

    rows = cur.fetchall()
    conn.close()
    return rows

# --- Endpoints ---
@app.get("/search")
def search(q: Optional[str] = Query(None),
           category: Optional[str] = Query(None),
           part_type: Optional[str] = Query(None),
           catalog_type: Optional[str] = Query(None),
           limit: int = 100):
    try:
        rows = query_db(q, category, part_type, catalog_type, limit)
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "catalog_type": r[1],
                "part_type": r[2],
                "part_number": r[3],
                "description": r[4],
                "category": r[5],
                "page": r[6],
                "image_url": f"/images/{Path(r[7]).name}" if r[7] else None,
                "pdf_url": get_pdf_url(r[8], r[6]),
                "pdf_page": r[6]
            })

        return {
            "query": q or "",
            "category_filter": category or "",
            "part_type_filter": part_type or "",
            "catalog_filter": catalog_type or "",
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
        cur.execute("""SELECT id, catalog_type, part_type, part_number, description,
                              category, page, image_path, page_text, pdf_path
                       FROM parts WHERE id=?""", (part_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Part not found")

        return {
            "id": row[0],
            "catalog_type": row[1],
            "part_type": row[2],
            "part_number": row[3],
            "description": row[4],
            "category": row[5],
            "page": row[6],
            "image_url": f"/images/{Path(row[7]).name}" if row[7] else None,
            "page_text": row[8],
            "pdf_url": get_pdf_url(row[9], row[6]),
            "pdf_page": row[6],
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

# --- Entrypoint ---
if __name__ == "__main__":
    print("Starting server on http://localhost:8000")
    print(f"Static directory: {STATIC_DIR}")
    print(f"PDF directory: {PDF_DIR}")
    print(f"Static files found:")
    for file in ["index.html", "styles.css", "app.js"]:
        path = STATIC_DIR / file
        print(f"  {file}: {'✓' if path.exists() else '✗'}")
    
    # List PDF files
    if PDF_DIR.exists():
        pdf_files = list(PDF_DIR.glob("*.pdf"))
        print(f"PDF files found ({len(pdf_files)}):")
        for pdf in pdf_files:
            print(f"  📄 {pdf.name}")
    else:
        print("PDF directory not found")
    
    uvicorn.run("app_toc:app", host="0.0.0.0", port=8000, reload=True)