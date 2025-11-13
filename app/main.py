import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import File, UploadFile, HTTPException
from pathlib import Path
import sqlite3
import json

# Internal imports
from app.utils.config import settings
from app.utils.logger import setup_logging
from app.routes import parts, guides, health,search
from app.services.db.queries import DatabaseManager
from app.services.storage.storage_service import StorageService
from app.services.storage.file_service import FileService


# ------------------------------------------------------------------------------
# [OK] Initialize FastAPI app
# ------------------------------------------------------------------------------
app = FastAPI(
    title=settings.FRONTEND_TITLE,
    description=settings.FRONTEND_DESCRIPTION,
    version="1.0.0"
)

# ------------------------------------------------------------------------------
# [OK] Setup logging and CORS
# ------------------------------------------------------------------------------
logger = setup_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# [OK] Define base paths and ensure directories exist
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = settings.TEMPLATES_DIR 

for folder in [DATA_DIR, STATIC_DIR, DATA_DIR / "pdfs", DATA_DIR / "page_images", DATA_DIR / "guides"]:
    folder.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# [OK] Mount static and data directories
# ------------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/pdfs", StaticFiles(directory=DATA_DIR / "pdfs"), name="pdfs")
app.mount("/images", StaticFiles(directory=DATA_DIR / "page_images"), name="images")
app.mount("/guides", StaticFiles(directory=DATA_DIR / "guides"), name="guides")

# ------------------------------------------------------------------------------
# [OK] Database connection function
# ------------------------------------------------------------------------------
def get_db_connection():
    DATABASE_URL = DATA_DIR / "catalog.db"
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------------------------------------------------------------------
# [OK]API ROUTES - SIMPLE AND WORKING
# ------------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    """Frontend configuration"""
    return {
        "maxDescriptionLength": 120,
        "maxApplicationsDisplay": 2,
        "searchDebounceMs": 300,
        "enableTechnicalGuides": True,
        "maxSearchResults": 50
    }

@app.get("/catalogs")
async def get_catalogs():
    """Get all catalog types"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT catalog_type as name 
            FROM parts 
            WHERE catalog_type IS NOT NULL AND catalog_type != ''
            ORDER BY catalog_type
        """)
        catalogs = [{"name": row[0]} for row in cur.fetchall()]
        conn.close()
        return {"catalogs": catalogs}
    except Exception as e:
        logger.error(f"Error fetching catalogs: {e}")
        return {"catalogs": []}

@app.get("/categories")
async def get_categories():
    """Get all categories"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT category 
            FROM parts 
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
        """)
        categories = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return {"categories": []}

@app.get("/part_types")
async def get_part_types():
    """Get all part types"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT part_type 
            FROM parts 
            WHERE part_type IS NOT NULL AND part_type != ''
            ORDER BY part_type
        """)
        part_types = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"part_types": part_types}
    except Exception as e:
        logger.error(f"Error fetching part types: {e}")
        return {"part_types": []}

@app.get("/search")
async def search_parts(
    q: str = "",
    category: str = "", 
    part_type: str = "",
    catalog_type: str = "",
    content_type: str = "all",
    limit: int = 50
):
    """Search parts with filters"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build query
        query = "SELECT * FROM parts WHERE 1=1"
        params = []
        
        if q:
            query += " AND (part_number LIKE ? OR description LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if part_type:
            query += " AND part_type = ?"
            params.append(part_type)
            
        if catalog_type:
            query += " AND catalog_type = ?"
            params.append(catalog_type)
        
        query += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        results = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        # Format for frontend
        formatted_results = []
        for part in results:
            applications = []
            if part.get('applications'):
                applications = [app.strip() for app in part['applications'].split(';') if app.strip()]
            
            formatted_part = {
                "id": part["id"],
                "part_number": part["part_number"],
                "description": part["description"],
                "category": part["category"],
                "part_type": part["part_type"],
                "catalog_type": part["catalog_type"],
                "page": part["page"],
                "image_url": f"/images/{part['image_path']}" if part.get('image_path') else None,
                "pdf_url": f"/pdfs/{part['pdf_path']}" if part.get('pdf_path') else None,
                "applications": applications
            }
            formatted_results.append(formatted_part)
            
        return {"results": formatted_results}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"results": []}

@app.get("/technical-guides")
async def get_technical_guides():
    """Get technical guides"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM technical_guides WHERE is_active = 1")
        guides = [dict(row) for row in cur.fetchall()]
        conn.close()
        return {"guides": guides}
    except Exception as e:
        logger.error(f"Error fetching guides: {e}")
        return {"guides": []}
    
@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), category: str = "catalogs"):
    """Upload PDF to storage (local or S3)"""
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Upload to storage
        file_key = await storage_service.upload_pdf(temp_path, category)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if file_key:
            url = storage_service.get_pdf_url(file_key)
            return {
                "file_key": file_key, 
                "download_url": url, 
                "message": "File uploaded successfully",
                "storage_type": "s3" if storage_service.use_s3 else "local"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to upload file")
            
    except Exception as e:
        logger.error(f"Error uploading PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/storage/files")
async def list_storage_files(prefix: str = ""):
    """List files in storage"""
    try:
        if storage_service.use_s3:
            files = storage_service.s3.list_objects(prefix)
            return {"files": files, "storage_type": "s3"}
        else:
            files = storage_service.local.list_files(prefix)
            return {"files": [str(f) for f in files], "storage_type": "local"}
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return {"files": [], "error": str(e)}

@app.get("/api/storage/status")
async def storage_status():
    """Get storage configuration status"""
    return {
        "use_s3": storage_service.use_s3,
        "local_data_dir": str(storage_service.local.data_dir) if hasattr(storage_service.local, 'data_dir') else None,
        "s3_bucket": storage_service.s3.bucket_name if hasattr(storage_service.s3, 'bucket_name') else None
    }   


    
# ------------------------------------------------------------------------------
# [OK] Template configuration (for base.html + index.html via Jinja2)
# ------------------------------------------------------------------------------
templates = Jinja2Templates(directory="app/templates")

# ------------------------------------------------------------------------------
# [OK] Include routers
# ------------------------------------------------------------------------------
app.include_router(search.router, tags=["search"])
app.include_router(guides.router, prefix="/api/guides", tags=["guides"])
app.include_router(parts.router, prefix="/api/parts", tags=["parts"])
app.include_router(health.router, prefix="/api/health", tags=["health"])

# ------------------------------------------------------------------------------
# [OK] Frontend serving routes
# ------------------------------------------------------------------------------
@app.get("/")
async def serve_frontend():
    """Serve main SPA index file."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        logger.error(f"Index file not found at {index_path}")
        return {"error": "Frontend not built or missing index.html"}
    return FileResponse(index_path)

@app.get("/search")
async def search_parts(
    q: str = "",
    category: str = "", 
    part_type: str = "",
    catalog_type: str = "",
    content_type: str = "all",
    limit: int = 50
):
    """Search parts with filters"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build query
        query = "SELECT * FROM parts WHERE 1=1"
        params = []
        
        if q and q.strip():
            query += " AND (part_number LIKE ? OR description LIKE ?)"
            search_term = f"%{q.strip()}%"
            params.extend([search_term, search_term])
        
        if category and category.strip():
            query += " AND category = ?"
            params.append(category.strip())
        
        if part_type and part_type.strip():
            query += " AND part_type = ?"
            params.append(part_type.strip())
            
        if catalog_type and catalog_type.strip():
            query += " AND catalog_type = ?"
            params.append(catalog_type.strip())
        
        query += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        results = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        # Format for frontend
        formatted_results = []
        for part in results:
            applications = []
            if part.get('applications'):
                applications = [app.strip() for app in part['applications'].split(';') if app.strip()]
            
            # FIX: Use correct image path - check if image exists
            image_path = None
            if part.get('image_path'):
                image_filename = part['image_path']
                # If it's already a full path, extract just the filename
                if '/' in image_filename:
                    image_filename = image_filename.split('/')[-1]
                image_path = f"/images/{image_filename}"
            
            formatted_part = {
                "id": part["id"],
                "part_number": part["part_number"],
                "description": part["description"],
                "category": part["category"],
                "part_type": part["part_type"],
                "catalog_type": part["catalog_type"],
                "page": part["page"],
                "image_url": image_path,
                "pdf_url": f"/pdfs/{part['pdf_path']}" if part.get('pdf_path') else None,
                "applications": applications
            }
            formatted_results.append(formatted_part)
            
        return {"results": formatted_results}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"results": []}

@app.get("/guides/{path:path}")
async def serve_guide_routes(path: str):
    """SPA catch-all for guide routes."""
    return FileResponse(STATIC_DIR / "index.html")
# ------------------------------------------------------------------------------
# [OK] Debug endpoints
# ------------------------------------------------------------------------------
@app.get("/api/debug/status")
async def debug_status():
    """Debug endpoint to check API status"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM parts")
        parts_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT catalog_type) FROM parts WHERE catalog_type IS NOT NULL")
        catalog_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT category) FROM parts WHERE category IS NOT NULL")
        category_count = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "online",
            "database": str(DATA_DIR / "catalog.db"),
            "parts_count": parts_count,
            "catalog_types": catalog_count,
            "categories": category_count
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    
@app.get("/api/parts/{part_id}")
async def get_part_details(part_id: int):
    """Get detailed part information"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM parts 
            WHERE id = ?
        """, (part_id,))
        
        part = cur.fetchone()
        conn.close()
        
        if not part:
            return {"error": "Part not found"}
        
        part_dict = dict(part)
        
        # Format applications
        applications = []
        if part_dict.get('applications'):
            applications = [app.strip() for app in part_dict['applications'].split(';') if app.strip()]
        
        # Format OE numbers
        oe_numbers = []
        if part_dict.get('oe_numbers'):
            oe_numbers = [oe.strip() for oe in part_dict['oe_numbers'].split(';') if oe.strip()]
        
        # Format specifications
        specifications = {}
        if part_dict.get('specifications'):
            try:
                specifications = json.loads(part_dict['specifications'])
            except:
                specifications = {"raw": part_dict['specifications']}
        
        # Build response
        formatted_part = {
            "id": part_dict["id"],
            "part_number": part_dict["part_number"],
            "description": part_dict["description"],
            "category": part_dict["category"],
            "part_type": part_dict["part_type"],
            "catalog_type": part_dict["catalog_type"],
            "page": part_dict["page"],
            "image_url": f"/images/{part_dict['image_path']}" if part_dict.get('image_path') else None,
            "pdf_url": f"/pdfs/{part_dict['pdf_path']}" if part_dict.get('pdf_path') else None,
            "applications": applications,
            "oe_numbers": oe_numbers,
            "specifications": specifications,
            "features": part_dict.get('features'),
            "machine_info": part_dict.get('machine_info')
        }
        
        return formatted_part
        
    except Exception as e:
        logger.error(f"Error fetching part {part_id}: {e}")
        return {"error": "Failed to fetch part details"}

@app.get("/api/debug/images")
async def debug_images():
    """Debug endpoint to check image files"""
    images_dir = DATA_DIR / "page_images"
    image_files = list(images_dir.glob("*.*"))
    
    return {
        "images_dir": str(images_dir),
        "total_images": len(image_files),
        "sample_images": [f.name for f in image_files[:10]],
        "static_mount": "/images"
    }

@app.get("/api/debug/parts-with-images")
async def debug_parts_with_images():
    """Check which parts have images"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, part_number, image_path 
            FROM parts 
            WHERE image_path IS NOT NULL 
            LIMIT 10
        """)
        
        parts_with_images = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return {
            "parts_with_images": parts_with_images,
            "count": len(parts_with_images)
        }
    except Exception as e:
        return {"error": str(e)}
    
    
@app.get("/api/parts/{part_id}/guides")
async def get_part_guides(part_id: int):
    """Get technical guides for a specific part"""
    try:
        # First get the part number
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT part_number FROM parts WHERE id = ?", (part_id,))
        part = cur.fetchone()
        conn.close()
        
        if not part:
            return {"guides": []}
        
        part_number = part['part_number']
        
        # Get guides for this part
        guide_extractor = GuideExtractor()
        guides = guide_extractor.get_guides_for_part(part_number)
        
        # Format for frontend
        formatted_guides = []
        for guide in guides:
            formatted_guide = {
                "id": guide["id"],
                "display_name": guide["display_name"],
                "description": guide["description"],
                "category": guide["category"],
                "confidence_score": guide.get("confidence_score", 1.0),
                "sections": guide.get("template_fields", {}).get("sections", [])[:3],  # First 3 sections
                "key_specifications": guide.get("template_fields", {}).get("key_specifications", {})
            }
            formatted_guides.append(formatted_guide)
        
        return {"guides": formatted_guides}
        
    except Exception as e:
        logger.error(f"Error fetching guides for part {part_id}: {e}")
        return {"guides": []}

@app.get("/api/guides/{guide_id}")
async def get_guide_details(guide_id: int):
    """Get detailed guide information"""
    try:
        guide_extractor = GuideExtractor()
        guide_data = guide_extractor.get_guide_content(guide_id)
        
        if not guide_data:
            return {"error": "Guide not found"}
        
        return {
            "guide": guide_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching guide {guide_id}: {e}")
        return {"error": "Failed to fetch guide"}
# ------------------------------------------------------------------------------
# [OK] Startup event
# ------------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("Knowledge Base API starting...")
    logger.info(f"Static directory: {STATIC_DIR}")
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info("API endpoints ready!")

# ------------------------------------------------------------------------------
# [OK] Local development entrypoint
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )