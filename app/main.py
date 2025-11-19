import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import sqlite3
import json
from datetime import datetime

# Internal imports
from app.utils.config import settings
from app.utils.logger import setup_logging
from app.routes import guides, health, parts  # Import parts router

# ------------------------------------------------------------------------------
# Initialize FastAPI app
# ------------------------------------------------------------------------------
app = FastAPI(
    title=settings.FRONTEND_TITLE,
    description=settings.FRONTEND_DESCRIPTION,
    version="1.0.0"
)

logger = setup_logging()

# ------------------------------------------------------------------------------
# CORS Setup
# ------------------------------------------------------------------------------
# Restrict CORS in production
allowed_origins = ["http://localhost:3000", "https://yourdomain.com"] if not settings.DEBUG else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Add file validation to upload endpoint
ALLOWED_EXTENSIONS = {'.pdf'}

@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), category: str = "catalogs"):
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Invalid file type")
    
# ------------------------------------------------------------------------------
# Define data directories
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

# Ensure directory structure
for folder in [
    DATA_DIR,
    STATIC_DIR,
    DATA_DIR / "pdfs",
    DATA_DIR / "guides",
    DATA_DIR / "part_images"  # All images go directly here
]:
    folder.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# Mount Static Directories
# ------------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/pdfs", StaticFiles(directory=DATA_DIR / "pdfs"), name="pdfs")
app.mount("/part_images", StaticFiles(directory=DATA_DIR / "part_images"), name="part_images")
app.mount("/guides", StaticFiles(directory=DATA_DIR / "guides"), name="guides")

# ------------------------------------------------------------------------------
# Include Routers
# ------------------------------------------------------------------------------
app.include_router(parts.router)  # Include parts router with /api prefix
app.include_router(guides.router, prefix="/api/guides", tags=["guides"])
app.include_router(health.router, prefix="/api/health", tags=["health"])

# ------------------------------------------------------------------------------
# DB Connection Helper
# ------------------------------------------------------------------------------
def get_db_connection():
    DATABASE_URL = DATA_DIR / "catalog.db"
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------------------------------------------------------------------
# Legacy endpoints for frontend compatibility
# ------------------------------------------------------------------------------
@app.get("/api/search/categories")
async def get_search_categories():
    """Delegate to parts router"""
    from app.routes.parts import get_categories
    return await get_categories()

@app.get("/api/search/part_types")
async def get_search_part_types():
    """Delegate to parts router"""
    from app.routes.parts import get_part_types
    return await get_part_types()

@app.get("/api/search/catalogs")
async def get_search_catalogs():
    """Delegate to parts router"""
    from app.routes.parts import get_catalogs
    return await get_catalogs()

# ------------------------------------------------------------------------------
# LEGACY SEARCH ENDPOINT - For frontend compatibility
# ------------------------------------------------------------------------------
@app.get("/search")
async def legacy_search(
    q: str = "",
    category: str = "",
    partType: str = "",
    catalogType: str = "",
    limit: int = 50
):
    """
    Legacy endpoint that maps old parameter names to new ones
    This handles the frontend calls to /search?partType=...&catalogType=...
    """
    # Import and use the search_parts function from parts router
    from app.routes.parts import search_parts
    return await search_parts(
        q=q,
        category=category,
        part_type=partType,  # Map partType → part_type
        catalog_type=catalogType,  # Map catalogType → catalog_type
        limit=limit
    )

# ------------------------------------------------------------------------------
# Technical Guides List
# ------------------------------------------------------------------------------
@app.get("/technical-guides")
async def get_technical_guides():
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM technical_guides WHERE is_active = 1")
            guides = [dict(r) for r in cur.fetchall()]
            return {"guides": guides}
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"guides": []}

# ------------------------------------------------------------------------------
# Part Guides Endpoint (app.js expects this)
# ------------------------------------------------------------------------------
@app.get("/api/parts/{part_id}/guides")
async def get_part_guides(part_id: int):
    """Endpoint that app.js expects for part technical guides"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT tg.* FROM technical_guides tg
            JOIN part_guides pg ON tg.id = pg.guide_id
            WHERE pg.part_id = ?
        """, (part_id,))
        guides = [dict(r) for r in cur.fetchall()]
        conn.close()
        
        # Format guides as expected by frontend
        formatted_guides = []
        for guide in guides:
            # Parse sections and key_specifications if they are JSON strings
            sections = guide.get("sections", [])
            if isinstance(sections, str):
                try:
                    sections = json.loads(sections)
                except:
                    sections = []
            
            key_specifications = guide.get("key_specifications", {})
            if isinstance(key_specifications, str):
                try:
                    key_specifications = json.loads(key_specifications)
                except:
                    key_specifications = {}
            
            formatted_guides.append({
                "id": guide["id"],
                "display_name": guide.get("name", guide.get("display_name", "Technical Guide")),
                "description": guide.get("description", ""),
                "confidence_score": float(guide.get("confidence_score", 0.9)),
                "sections": sections,
                "key_specifications": key_specifications
            })
        
        return {"guides": formatted_guides}
    except Exception as e:
        logger.error(f"Error getting guides for part {part_id}: {e}")
        return {"guides": []}

# ------------------------------------------------------------------------------
# Upload PDF endpoint
# ------------------------------------------------------------------------------
@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), category: str = "catalogs"):
    try:
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        os.unlink(temp_path)
        return {"file_key": file.filename, "message": "Upload processed"}

    except Exception as e:
        logger.error(e)
        raise HTTPException(500, str(e))

# ------------------------------------------------------------------------------
# SPA Frontend
# ------------------------------------------------------------------------------
@app.get("/")
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return {"error": "index.html missing"}
    return FileResponse(index_path)

@app.get("/guides/{path:path}")
async def serve_guides_spa(path: str):
    return FileResponse(STATIC_DIR / "index.html")

# ------------------------------------------------------------------------------
# Root-level Image Fallback Handler
# ------------------------------------------------------------------------------
import re

def normalize_image_filename(filename: str) -> str:
    """
    Normalize image filename by removing leading zeros from numeric suffixes
    Example: img010.png -> img10.png, Stemco_Gaff_p52_img010.png -> Stemco_Gaff_p52_img10.png
    """
    name, ext = os.path.splitext(filename)
    
    # Pattern to find numeric suffixes after the last underscore
    # Matches patterns like: _img010, _img001, etc.
    pattern = r'(_[a-zA-Z]*)0+(\d+)$'
    match = re.search(pattern, name)
    
    if match:
        prefix = match.group(1)  # _img
        num = match.group(2)     # 10
        normalized_suffix = f"{prefix}{num}"
        # Replace the original suffix with normalized one
        normalized_name = name[:match.start()] + normalized_suffix
        return f"{normalized_name}{ext}"
    
    return filename

@app.get("/{filename:path}")
async def root_image_fallback(filename: str):
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
    
    if any(filename.lower().endswith(ext) for ext in image_extensions):
        # Try original filename first
        image_path = DATA_DIR / "part_images" / filename
        if image_path.exists():
            return FileResponse(image_path)
        
        # Try normalized filename (without leading zeros)
        normalized_name = normalize_image_filename(filename)
        if normalized_name != filename:
            normalized_path = DATA_DIR / "part_images" / normalized_name
            if normalized_path.exists():
                return FileResponse(normalized_path)
        
        # Fallback: check all extensions with normalized base name
        base_name = normalize_image_filename(Path(filename).stem)
        for ext in image_extensions:
            alt_path = DATA_DIR / "part_images" / f"{base_name}{ext}"
            if alt_path.exists():
                return FileResponse(alt_path)
        
        raise HTTPException(status_code=404, detail="Image not found")
    
    raise HTTPException(status_code=404, detail="Not found")

# ------------------------------------------------------------------------------
# Health Check Endpoint (for frontend compatibility)
# ------------------------------------------------------------------------------
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "parts-catalog",
        "timestamp": datetime.utcnow().isoformat()
    }

# ------------------------------------------------------------------------------
# Startup Event
# ------------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    logger.info("API Ready.")
    
    # Log normalized image names for debugging
    images_dir = DATA_DIR / "part_images"
    if images_dir.exists():
        image_files = []
        for pattern in ["*.png", "*.jpg", "*.jpeg"]:
            image_files.extend(images_dir.glob(pattern))
        
        logger.info(f"Found {len(image_files)} images in part_images directory")
        if image_files:
            normalized_samples = [normalize_image_filename(f.name) for f in image_files[:5]]
            logger.info(f"Normalized sample images: {normalized_samples}")
            
# ------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)