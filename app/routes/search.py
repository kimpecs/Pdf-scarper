from fastapi import APIRouter, HTTPException, Query
from app.services.db.queries import DatabaseManager
from services.pdf_processing.extract_guides import GuideExtractor
from services.pdf_processing.extract_catalog import CatalogExtractor


router = APIRouter(prefix="/api/search", tags=["Search"])

db = DatabaseManager()
guide_extractor = GuideExtractor()
catalog_extractor = CatalogExtractor()

@router.get("/")
def search_parts(q: str = Query(..., description="Search by part number or keyword")):
    """
    Search both catalog and guide data by part number or keyword
    """
    conn = db.get_connection()
    cur = conn.cursor()
    
    # Search by part number or description
    cur.execute("""
        SELECT * FROM parts_catalog
        WHERE part_number LIKE ? OR description LIKE ?
        ORDER BY part_number ASC
    """, (f"%{q}%", f"%{q}%"))
    
    parts = [dict(row) for row in cur.fetchall()]

    # Attach related guides for each part
    for part in parts:
        guides = guide_extractor.get_guides_for_part(part["part_number"])
        part["guides"] = [
            {
                "id": g["id"],
                "display_name": g["display_name"],
                "category": g["category"],
                "pdf_path": g["pdf_path"],
                "confidence": g.get("confidence_score", 1.0)
            }
            for g in guides
        ]

    conn.close()
    return {"query": q, "results": parts}


@router.get("/search")
async def search_parts(
    q: str = Query(None),
    category: str = Query(None), 
    part_type: str = Query(None),
    catalog_type: str = Query(None),
    content_type: str = Query("all"),
    limit: int = Query(50)
):
    try:
        results = db.search_parts(
            query=q,
            category=category,
            part_type=part_type,
            catalog_name=catalog_type,
            limit=limit
        )
        
       
        formatted_results = []
        for part in results:
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
                "applications": part.get('applications', '').split(';') if part.get('applications') else []
            }
            formatted_results.append(formatted_part)
            
        return {"results": formatted_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/catalogs")
async def get_catalogs():
    try:
        # Get unique catalog types from your parts data
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT catalog_type FROM parts WHERE catalog_type IS NOT NULL")
        catalogs = [{"name": row[0]} for row in cur.fetchall()]
        conn.close()
        return {"catalogs": catalogs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
async def get_categories():
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM parts WHERE category IS NOT NULL")
        categories = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/part_types")
async def get_part_types():
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT part_type FROM parts WHERE part_type IS NOT NULL")
        part_types = [row[0] for row in cur.fetchall()]
        conn.close()
        return {"part_types": part_types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/config")
async def get_config():
    return {
        "maxDescriptionLength": 120,
        "maxApplicationsDisplay": 2,
        "searchDebounceMs": 300,
        "enableTechnicalGuides": True,
        "maxSearchResults": 50
    }