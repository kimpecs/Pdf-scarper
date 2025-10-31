from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import json
from typing import Optional, List
from pathlib import Path


templates = Jinja2Templates(directory="app/templates")

# Import from app modules
from app.services.db.queries import DatabaseManager
from app.utils.file_utils import get_pdf_url
from app.utils.logger import setup_logging
from app.utils.config import settings

logger = setup_logging()
router = APIRouter()
db_manager = DatabaseManager()

@router.get("/search")
async def search_parts(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    part_type: Optional[str] = Query(None),
    catalog_type: Optional[str] = Query(None),
    content_type: Optional[str] = Query("all"),
    limit: int = Query(100, ge=1, le=1000)
):
    """Search parts with filters"""
    try:
        if content_type == "guides":
            return {
                "query": q or "",
                "filters": {
                    "category": category,
                    "part_type": part_type,
                    "catalog_type": catalog_type,
                    "content_type": content_type
                },
                "count": 0,
                "results": []
            }
        
        results = db_manager.search_parts(q, category, part_type, catalog_type, limit)
        
        # Enhance results with URLs
        enhanced_results = []
        for part in results:
            part['image_url'] = f"/images/{Path(part['image_path']).name}" if part.get('image_path') else None
            part['pdf_url'] = get_pdf_url(part.get('pdf_path'), part.get('page', 1))
            enhanced_results.append(part)
        
        return {
            "query": q or "",
            "filters": {
                "category": category,
                "part_type": part_type,
                "catalog_type": catalog_type,
                "content_type": content_type
            },
            "count": len(enhanced_results),
            "results": enhanced_results
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@router.get("/parts/{part_id}")
async def get_part(part_id: int):
    """Get detailed part information"""
    try:
        part = db_manager.get_part_by_id(part_id)
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        
        # Enhance with URLs
        part['image_url'] = f"/images/{Path(part['image_path']).name}" if part.get('image_path') else None
        part['pdf_url'] = get_pdf_url(part.get('pdf_path'), part.get('page', 1))
        
        return part
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting part: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/categories")
async def get_categories():
    """Get all categories with counts"""
    try:
        categories = db_manager.get_categories_with_counts()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/catalogs")
async def get_catalogs():
    """Get all available catalogs"""
    try:
        conn = db_manager.get_connection()
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
        logger.error(f"Error getting catalogs: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@router.get("/guides/{guide_name}")
async def get_technical_guide(request: Request, guide_name: str):
    """Get technical guide HTML page"""
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT guide_name, display_name, description, category, template_fields
            FROM technical_guides 
            WHERE guide_name = ?
        """, (guide_name,))
        
        guide_row = cur.fetchone()
        if not guide_row:
            raise HTTPException(status_code=404, detail="Guide not found")
        
        # Parse template fields
        template_fields = json.loads(guide_row[4]) if guide_row[4] else {}
        
        # Get related parts based on guide content
        cur.execute("""
            SELECT DISTINCT p.id, p.part_number, p.description, p.category
            FROM parts p
            WHERE p.description LIKE ? OR p.category = ?
            LIMIT ?
        """, (f'%{guide_row[1]}%', guide_row[3], settings.MAX_RELATED_PARTS))
        
        related_parts = []
        for row in cur.fetchall():
            related_parts.append({
                'id': row[0],
                'part_number': row[1],
                'description': row[2],
                'category': row[3]
            })
        
        # Get related guides
        cur.execute("""
            SELECT guide_name, display_name 
            FROM technical_guides 
            WHERE category = ? AND guide_name != ?
            LIMIT 5
        """, (guide_row[3], guide_name))
        
        related_guides = []
        for row in cur.fetchall():
            related_guides.append({
                'guide_name': row[0],
                'display_name': row[1]
            })
        
        conn.close()
        
        return templates.TemplateResponse("technical_guide.html", {
            "request": request,
            "guide_title": guide_row[1],
            "description": guide_row[2],
            "category": guide_row[3],
            "guide_name": guide_row[0],
            "related_parts": related_parts,
            "related_guides": related_guides,
            **template_fields
        })
        
    except Exception as e:
        logger.error(f"Error getting guide: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/guides/{guide_name}/download")
async def download_technical_guide(guide_name: str):
    """Download technical guide PDF"""
    try:
        guide_path = Path("app/data/guides") / f"{guide_name}.pdf"
        if not guide_path.exists():
            raise HTTPException(status_code=404, detail="Guide PDF not found")
        
        return FileResponse(
            guide_path,
            media_type='application/pdf',
            filename=f"{guide_name}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading guide: {e}")
        raise HTTPException(status_code=500, detail=f"File error: {str(e)}")