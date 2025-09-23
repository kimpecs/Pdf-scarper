# app_toc.py
import sqlite3
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn
from typing import List, Optional

DB_PATH = Path("catalog.db")
IMAGES_DIR = Path("page_images")

app = FastAPI(title="Hydraulic Brakes Catalog Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, JS, images) from static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve page images
app.mount("/images", StaticFiles(directory="page_images"), name="images")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serve the main index.html from static folder"""
    try:
        # Try to serve from static folder first
        index_path = Path("static") / "index.html"
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        try:
            # Fallback to root directory
            with open("index.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            # Final fallback - basic HTML response
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
                        <p>Server is running, but index.html was not found in expected locations.</p>
                        <p>Expected paths:</p>
                        <ul>
                            <li><code>static/index.html</code></li>
                            <li><code>index.html</code> (root directory)</li>
                        </ul>
                        <p>API endpoints:</p>
                        <ul>
                            <li><a href="/health">/health</a> - Health check</li>
                            <li><a href="/categories">/categories</a> - List categories</li>
                            <li><a href="/search?q=D50">/search?q=D50</a> - Search parts</li>
                            <li><a href="/test">/test</a> - System test</li>
                        </ul>
                    </div>
                </body>
                </html>
            """)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Server is running"}

@app.get("/test")
def test_endpoint():
    """Comprehensive test endpoint to debug the system"""
    results = {
        "server_status": "running",
        "database_connection": "unknown",
        "tables_exist": "unknown",
        "parts_count": 0,
        "categories_count": 0,
        "sample_parts": [],
        "file_locations": {}
    }
    
    try:
        # Test file locations
        results["file_locations"] = {
            "static_index_html": Path("static/index.html").exists(),
            "root_index_html": Path("index.html").exists(),
            "database_file": DB_PATH.exists(),
            "images_dir": IMAGES_DIR.exists()
        }
        
        # Test database connection
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        results["database_connection"] = "success"
        
        # Test if tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parts'")
        results["tables_exist"] = "yes" if cur.fetchone() else "no"
        
        # Get parts count
        cur.execute("SELECT COUNT(*) FROM parts")
        results["parts_count"] = cur.fetchone()[0]
        
        # Get categories count
        cur.execute("SELECT COUNT(DISTINCT category) FROM parts")
        results["categories_count"] = cur.fetchone()[0]
        
        # Get sample parts
        cur.execute("""
            SELECT part_type, part_number, category, page 
            FROM parts 
            ORDER BY page, part_number 
            LIMIT 5
        """)
        results["sample_parts"] = [
            {"type": row[0], "number": row[1], "category": row[2], "page": row[3]}
            for row in cur.fetchall()
        ]
        
        conn.close()
        
    except Exception as e:
        results["error"] = str(e)
        results["database_connection"] = "failed"
    
    return results

@app.get("/categories")
def get_categories():
    """Get unique categories for filter dropdown"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM parts WHERE category IS NOT NULL ORDER BY category")
        categories = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/part_types")
def get_part_types():
    """Get unique part types for filter"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT part_type FROM parts WHERE part_type IS NOT NULL ORDER BY part_type")
        part_types = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"part_types": part_types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def query_db(q: str = None, category: str = None, part_type: str = None, limit=100):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if not q:
        # Return all parts with filters
        sql = "SELECT id, part_type, part_number, description, category, page, image_path FROM parts WHERE 1=1"
        params = []
        
        if category and category != "null":
            sql += " AND category=?"
            params.append(category)
        if part_type and part_type != "null":
            sql += " AND part_type=?"
            params.append(part_type)
            
        sql += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        cur.execute(sql, tuple(params))
        
    else:
        # If q looks like a specific part number pattern
        if q.upper().startswith(('D', '600-', 'CH')):
            sql = """SELECT id, part_type, part_number, description, category, page, image_path 
                     FROM parts WHERE part_number LIKE ?"""
            params = [f"{q}%"]
            
            if category and category != "null":
                sql += " AND category=?"
                params.append(category)
            if part_type and part_type != "null":
                sql += " AND part_type=?"
                params.append(part_type)
                
            sql += " LIMIT ?"
            params.append(limit)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            if rows:
                conn.close()
                return rows

        # Fallback: full-text search using FTS5
        safe_q = q.replace("'", "''")
        sql = """SELECT p.id, p.part_type, p.part_number, p.description, p.category, p.page, p.image_path 
                 FROM parts p JOIN parts_fts f ON p.id = f.rowid 
                 WHERE parts_fts MATCH ?"""
        params = [safe_q]
        
        if category and category != "null":
            sql += " AND p.category=?"
            params.append(category)
        if part_type and part_type != "null":
            sql += " AND p.part_type=?"
            params.append(part_type)
            
        sql += " LIMIT ?"
        params.append(limit)
        cur.execute(sql, tuple(params))

    rows = cur.fetchall()
    conn.close()
    return rows

@app.get("/search")
def search(q: Optional[str] = Query(None), 
           category: Optional[str] = Query(None), 
           part_type: Optional[str] = Query(None), 
           limit: int = 100):
    try:
        rows = query_db(q, category=category, part_type=part_type, limit=limit)
        results = []
        for id_, pt, pn, desc, cat, page, image_path in rows:
            results.append({
                "id": id_,
                "part_type": pt,
                "part_number": pn,
                "description": desc,
                "category": cat,
                "page": page,
                "image_url": f"/images/{Path(image_path).name}" if image_path else None
            })
        return {
            "query": q or "",
            "category_filter": category or "",
            "part_type_filter": part_type or "",
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/part/{part_id}")
def get_part(part_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, part_type, part_number, description, category, page, image_path, page_text FROM parts WHERE id=?", (part_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Part not found")
        id_, pt, pn, desc, cat, page, image_path, page_text = row
        return {
            "id": id_,
            "part_type": pt,
            "part_number": pn,
            "description": desc,
            "category": cat,
            "page": page,
            "image_url": f"/images/{Path(image_path).name}" if image_path else None,
            "page_text": page_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/images/{image_filename}")
def get_image(image_filename: str):
    path = IMAGES_DIR / image_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")

if __name__ == "__main__":
    print("Starting server on http://localhost:8000")
    print("Available endpoints:")
    print("  http://localhost:8000/          - Main application")
    print("  http://localhost:8000/health    - Health check")
    print("  http://localhost:8000/test      - System test")
    print("  http://localhost:8000/categories - List categories")
    print("  http://localhost:8000/search?q=D50 - Search example")
    uvicorn.run("app_toc:app", host="0.0.0.0", port=8000, reload=True)