from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pathlib import Path
import os

from app.services.db.queries import DatabaseManager
from services.pdf_processing.extract_guides import GuideExtractor
from app.utils.file_utils import get_pdf_url
from app.utils.logger import setup_logging

router = APIRouter(prefix="/api", tags=["Search"])

logger = setup_logging()
db = DatabaseManager()
guide_extractor = GuideExtractor()

def row_to_dict(row):
    """Convert sqlite3.Row to dictionary"""
    if hasattr(row, '_fields'):  # sqlite3.Row
        return {key: row[key] for key in row._fields}
    return dict(row)

def get_image_url(image_path: str) -> Optional[str]:
    """Generate proper image URL for flat file structure"""
    if not image_path:
        return None
    
    # Extract just the filename from any path structure
    clean_path = image_path.replace("\\", "/")
    filename = Path(clean_path).name
    
    # Return the URL path to /images/ (mounted static directory)
    return f"/images/{filename}"

# -------------------------------------------------------------
# 1) Fixed /search endpoint
# -------------------------------------------------------------
@router.get("/search")
async def search_parts(
    q: Optional[str] = Query(None, description="Search term for part number or description"),
    category: Optional[str] = Query(None),
    part_type: Optional[str] = Query(None),
    catalog_type: Optional[str] = Query(None),
    content_type: str = Query("all"),
    limit: int = Query(50, ge=1, le=1000)
):
    try:
        # If user wants only guides, return empty for now
        if content_type == "guides":
            return {
                "query": q or "",
                "filters": {
                    "category": category,
                    "part_type": part_type,
                    "catalog_type": catalog_type,
                    "content_type": content_type,
                },
                "count": 0,
                "results": [],
            }

        results = db.search_parts(
            query=q,
            category=category,
            part_type=part_type,
            catalog_name=catalog_type,
            limit=limit
        )

        formatted = []
        for row in results:
            part = row_to_dict(row)
            
            # Use the simplified image URL function - always return /images/filename
            image_url = get_image_url(part.get("image_path"))

            formatted.append({
                "id": part.get("id"),
                "part_number": part.get("part_number"),
                "description": part.get("description"),
                "category": part.get("category"),
                "part_type": part.get("part_type"),
                "catalog_type": part.get("catalog_type"),
                "page": part.get("page"),
                "image_url": image_url,
                "pdf_url": get_pdf_url(part.get("pdf_path"), part.get("page", 1)),
                "applications": [
                    a.strip() for a in part.get("applications", "").split(";")
                    if a.strip()
                ],
            })

        return {
            "query": q or "",
            "filters": {
                "category": category,
                "part_type": part_type,
                "catalog_type": catalog_type,
                "content_type": content_type,
            },
            "count": len(formatted),
            "results": formatted,
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")

# -------------------------------------------------------------
# 2) Add individual part endpoint
# -------------------------------------------------------------
@router.get("/parts/{part_id}")
async def get_part_detail(part_id: int):
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM parts WHERE id = ?
        """, (part_id,))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(404, "Part not found")
        
        part = row_to_dict(row)
        
        # Use the simplified image URL function - always return /images/filename
        part["image_url"] = get_image_url(part.get("image_path"))
            
        # Parse applications
        applications_str = part.get("applications", "")
        part["applications"] = [
            a.strip() for a in applications_str.split(";")
            if a.strip()
        ]
        
        return part
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching part {part_id}: {e}")
        raise HTTPException(500, f"Failed to fetch part: {str(e)}")

# -------------------------------------------------------------
# 3) Fixed /catalogs endpoint
# -------------------------------------------------------------
@router.get("/catalogs")
async def get_catalogs():
    try:
        conn = db.get_connection()
        cur = conn.cursor()

        # Fetch distinct catalog types
        cur.execute("""
            SELECT DISTINCT catalog_type FROM parts 
            WHERE catalog_type IS NOT NULL 
            ORDER BY catalog_type
        """)

        catalogs = [{"name": row[0]} for row in cur.fetchall()]
        conn.close()
        return {"catalogs": catalogs}

    except Exception as e:
        logger.error(f"Error fetching catalogs: {e}")
        raise HTTPException(500, "Failed to fetch catalogs")

# -------------------------------------------------------------
# 4) Add categories endpoint
# -------------------------------------------------------------
@router.get("/categories")
async def get_categories():
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM parts WHERE category IS NOT NULL ORDER BY category")
        categories = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(500, "Failed to fetch categories")

# -------------------------------------------------------------
# 5) Add part_types endpoint
# -------------------------------------------------------------
@router.get("/part_types")
async def get_part_types():
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT part_type FROM parts WHERE part_type IS NOT NULL ORDER BY part_type")
        part_types = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"part_types": part_types}
    except Exception as e:
        logger.error(f"Error fetching part types: {e}")
        raise HTTPException(500, "Failed to fetch part types")

# -------------------------------------------------------------
# 6) Add config endpoint
# -------------------------------------------------------------
@router.get("/config")
async def get_config():
    return {
        "maxDescriptionLength": 120,
        "maxApplicationsDisplay": 2,
        "searchDebounceMs": 300,
        "enableTechnicalGuides": True,
        "maxSearchResults": 50
    }