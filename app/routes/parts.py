import sqlite3
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
    if row is None:
        return {}
    if hasattr(row, '_fields') and hasattr(row, '_asdict'):
        try:
            return dict(row._asdict())
        except:
            return {key: row[key] for key in row._fields}
    if hasattr(row, '_fields'):
        try:
            return {key: row[key] for key in row._fields}
        except (TypeError, IndexError):
            return dict(row)
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
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute("""
                SELECT * FROM parts WHERE id = ?
            """, (part_id,))
            
            row = cur.fetchone()
            
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

# -------------------------------------------------------------
# 7) Enhanced Part Detail with Technical Guide Integration
# -------------------------------------------------------------
@router.get("/parts/{part_id}/enhanced")
async def get_enhanced_part_detail(part_id: int):
    """Get part details merged with technical guide information"""
    try:
        # Get basic part info
        conn = db.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(404, "Part not found")
        
        part = row_to_dict(row)
        
        # Get technical guides for this part
        cur.execute("""
            SELECT tg.*, pg.confidence_score 
            FROM technical_guides tg
            JOIN part_guides pg ON tg.id = pg.guide_id
            WHERE pg.part_id = ? AND tg.is_active = 1
            ORDER BY pg.confidence_score DESC
        """, (part_id,))
        
        guides = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        # Enhanced image URL
        part["image_url"] = get_image_url(part.get("image_path"))
        
        # Parse applications
        applications_str = part.get("applications", "")
        part["applications"] = [
            a.strip() for a in applications_str.split(";")
            if a.strip()
        ]
        
        # Merge with technical guide data
        enhanced_data = self._merge_with_technical_guides(part, guides)
        
        return enhanced_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching enhanced part {part_id}: {e}")
        raise HTTPException(500, f"Failed to fetch enhanced part: {str(e)}")

def _merge_with_technical_guides(self, part: Dict, guides: List[Dict]) -> Dict:
    """Merge part data with technical guide information"""
    enhanced = part.copy()
    
    # Initialize enhanced fields
    enhanced["introduction"] = ""
    enhanced["usage_info"] = []
    enhanced["specifications"] = {}
    enhanced["cross_references"] = []
    enhanced["technical_guides"] = []
    
    # Extract from part data first
    if part.get("description"):
        enhanced["introduction"] = part["description"]
    
    if part.get("applications"):
        enhanced["usage_info"].extend(part["applications"])
    
    # Extract from technical guides
    for guide in guides:
        # Add guide to list
        guide_summary = {
            "id": guide["id"],
            "display_name": guide.get("display_name", guide.get("guide_name", "")),
            "description": guide.get("description", ""),
            "confidence_score": guide.get("confidence_score", 0.5)
        }
        enhanced["technical_guides"].append(guide_summary)
        
        # Parse template fields if available
        template_fields = guide.get("template_fields")
        if template_fields and isinstance(template_fields, str):
            try:
                template_data = json.loads(template_fields)
                self._merge_template_data(enhanced, template_data)
            except:
                pass
    
    # Format cross references
    enhanced["cross_references"] = self._format_cross_references(part)
    
    return enhanced

def _merge_template_data(self, enhanced: Dict, template_data: Dict):
    """Merge data from guide template fields"""
    # Merge introduction
    if not enhanced["introduction"] and template_data.get("description"):
        enhanced["introduction"] = template_data["description"]
    
    # Merge usage info
    if template_data.get("sections"):
        for section in template_data["sections"]:
            if "usage" in section.get("title", "").lower() or "application" in section.get("title", "").lower():
                enhanced["usage_info"].append(section.get("content", ""))
    
    # Merge specifications
    if template_data.get("key_specifications"):
        enhanced["specifications"].update(template_data["key_specifications"])
    
    # Add any additional specifications from sections
    if template_data.get("sections"):
        for section in template_data["sections"]:
            if "specification" in section.get("title", "").lower():
                # Extract key-value pairs from section content
                specs = self._extract_specifications_from_text(section.get("content", ""))
                enhanced["specifications"].update(specs)

def _extract_specifications_from_text(self, text: str) -> Dict:
    """Extract specifications from text content"""
    specs = {}
    
    # Pattern for key-value specifications
    patterns = [
        r'(\w+)\s*[=:]\s*([^,\n]+)',  # key = value
        r'([^:]+):\s*([^\n]+)',       # key: value
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            key = match.group(1).strip()
            value = match.group(2).strip()
            if key and value and len(key) > 2:
                specs[key] = value
    
    return specs

def _format_cross_references(self, part: Dict) -> List[Dict]:
    """Format cross reference data"""
    cross_refs = []
    
    # Primary part
    cross_refs.append({
        "oem": "Primary",
        "part_number": part.get("part_number", ""),
        "alias": "Main Part",
        "compatible_vehicles": "All compatible applications"
    })
    
    # OE numbers if available
    if part.get("oe_numbers"):
        oe_numbers = [oe.strip() for oe in part["oe_numbers"].split(";") if oe.strip()]
        for oe in oe_numbers:
            cross_refs.append({
                "oem": "OEM",
                "part_number": oe,
                "alias": "Alternate",
                "compatible_vehicles": "OE specification"
            })
    
    return cross_refs